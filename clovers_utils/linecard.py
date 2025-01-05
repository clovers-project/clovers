import sys
import re
from pathlib import Path
from collections.abc import Iterable
from io import BytesIO
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL.ImageFont import FreeTypeFont
from PIL.Image import Image as IMG

match sys.platform:
    case "win32":
        FONT_PATH = "C:/Windows/Fonts"
    case "darwin":
        FONT_PATH = "/Library/Fonts"
    case "linux":
        FONT_PATH = "/usr/share/fonts"
    case _:
        raise ValueError("Unsupported platform")


class FontManager:
    """
    字体管理器
    """

    def __init__(self, font_name: str, fallback: list[str], size: Iterable[int] | None = None) -> None:
        path = self.find_font(font_name)
        if not path:
            raise ValueError(f"Font:{font_name} not found")
        self.path = path.absolute()
        self.font_name: str = font_name
        self.cmap = TTFont(path, recalcBBoxes=False, recalcTimestamp=False, fontNumber=0).getBestCmap()
        self.fallback: list[str] = fallback
        self.fallback_cmap = {}
        for fallback_name in self.fallback:
            fallback_path = self.find_font(fallback_name)
            if not fallback_path:
                continue
            self.fallback_cmap[fallback_path.absolute()] = TTFont(fallback_path, fontNumber=0).getBestCmap()

        self.font_def = {k: self.new_font(font_name, k) for k in size} if size else {}

    @property
    def fallback_paths(self) -> list[str]:
        return list(self.fallback_cmap.keys())

    def font(self, size: int):
        return self.font_def.get(size) or self.new_font(self.font_name, size)

    def new_font(self, name: str, size: int):
        return ImageFont.truetype(font=name, size=size, encoding="utf-8")

    @staticmethod
    def find_font(font_name: str, search_path=Path(FONT_PATH).absolute()):
        def check_font(font_file: Path, font_name: str):
            suffix = font_file.suffix.lower()
            if not suffix.endswith((".ttf", ".otf", ".ttc")):
                return False
            font_name = font_name.lower()
            if not font_name == font_file.stem.lower():
                return False
            try:
                TTFont(font_file, recalcBBoxes=False, recalcTimestamp=False, fontNumber=0)
            except:
                return False
            return True

        try:
            TTFont(font_name, recalcBBoxes=False, recalcTimestamp=False, fontNumber=0)
            return Path(font_name)
        except:
            pass

        for file in search_path.iterdir():
            if check_font(file, font_name):
                return file
        return None


def linecard_to_png(text: str, font_manager: FontManager, **kwargs):
    """
    文字转png
    """
    output = BytesIO()
    linecard(text, font_manager, **kwargs).save(output, format="png")
    return output


def remove_tag(text: str, pattern: re.Pattern):
    match = pattern.search(text)
    if match:
        start = match.start()
        end = match.end()
        return text[:start] + text[end:], text[start:end]
    else:
        return None


def line_wrap(line: str, width: int, font: FreeTypeFont, start: float = 0):
    text_x = start
    new_str = ""
    for char in line:
        text_x += font.getlength(char)
        if text_x > width:
            new_str += "\n" + char
            text_x = 0
        else:
            new_str += char
    return new_str


class Tag:
    def __init__(self, font, cmap, align="left") -> None:
        self.align: str = align
        self.font: FreeTypeFont = font
        self.cmap: dict = cmap
        self.color: str | None = None
        self.passport: bool = False
        self.noautowrap: bool = False
        self.nowrap: bool = False


class linecard_pattern:
    align = re.compile(r"\[left\]|\[right\]|\[center\]|\[pixel\]\[.*?\]")
    font = re.compile(r"\[font\]\[.*?\]\[.*?\]")
    color = re.compile(r"\[color\]\[.*?\]")
    passport = re.compile(r"\[passport\]")
    nowrap = re.compile(r"\[nowrap\]")
    noautowrap = re.compile(r"\[noautowrap\]")


def linecard(
    text: str,
    font_manager: FontManager,
    font_size: int,
    width: int | None = None,
    height: int | None = None,
    padding: tuple[int, int] = (20, 20),
    spacing: float = 1.2,
    bg_color: str | int = 0,
    autowrap: bool = False,
    canvas: IMG | None = None,
) -> IMG:
    """
    指定宽度单行文字
        ----:横线

        [left]靠左
        [right]靠右
        [center]居中
        [pixel][400]指定像素

        [font][font_name][font_size]指定字体

        [color][#000000]指定本行颜色

        [nowrap]不换行
        [noautowrap]不自动换行
        [passport]保持标记
    """
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    padding_x, padding_y = padding

    align = "left"

    font_def = font_manager.font(font_size)
    cmap_def = font_manager.cmap

    tag = Tag(font_def, cmap_def)

    x, max_x, y, charlist = (0.0, 0.0, 0.0, [])
    for line in lines:
        # 检查继承格式
        if tag.passport:
            tag.passport = False
        else:
            tag.__init__(font_def, cmap_def, align="nowrap" if tag.nowrap else "left")

        # 检查对齐格式
        if data := remove_tag(line, linecard_pattern.align):
            line, align = data
            if align.startswith("[pixel]["):
                tag.align = align[8:-1]
                x = 0
            else:
                tag.align = align[1:-1]

        if data := remove_tag(line, linecard_pattern.font):
            line, font = data
            if font.startswith("[font]["):
                font = font[7:-1]
                inner_font_name, inner_font_size = font.split("][", 1)
                inner_font_size = int(inner_font_size) if inner_font_size else font_size
                inner_font_name = inner_font_name or font_def.path
                try:
                    tag.font = ImageFont.truetype(font=inner_font_name, size=inner_font_size, encoding="utf-8")
                    tag.cmap = TTFont(tag.font.path, fontNumber=tag.font.index).getBestCmap()
                except OSError:
                    pass

        if data := remove_tag(line, linecard_pattern.color):
            line, color = data
            tag.color = color[8:-1]

        if data := remove_tag(line, linecard_pattern.noautowrap):
            line = data[0]
            tag.noautowrap = True

        if data := remove_tag(line, linecard_pattern.nowrap):
            line = data[0]
            tag.nowrap = True
        else:
            tag.nowrap = False

        if data := remove_tag(line, linecard_pattern.passport):
            line = data[0]
            tag.passport = True

        if autowrap and not tag.noautowrap and width and tag.font.getlength(line) > width:
            line = line_wrap(line, width - sum(padding), tag.font, x)

        if line == "----":
            inner_tmp = tag.font.size * spacing
            charlist.append([line, None, y, inner_tmp, tag.color, None])
            y += inner_tmp
        else:
            line_segs = line.split("\n")
            for seg in line_segs:
                for char in seg:
                    ord_char = ord(char)
                    inner_font = tag.font
                    if ord_char not in tag.cmap:
                        for (
                            fallback_font,
                            fallback_cmap,
                        ) in font_manager.fallback_cmap.items():
                            if ord_char in fallback_cmap:
                                inner_font = ImageFont.truetype(
                                    font=fallback_font,
                                    size=int(tag.font.size),
                                    encoding="utf-8",
                                )
                                break
                        else:
                            char = "□"
                    charlist.append([char, x, y, inner_font, tag.color, tag.align])
                    x += inner_font.getlength(char)
                max_x = max(max_x, x)
                x, y = (x, y) if tag.nowrap else (0, y + tag.font.size * spacing)

    width = width if width else int(max_x + padding_x * 2)
    height = height if height else int(y + padding_y * 2)
    canvas = canvas if canvas else Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(canvas)

    for i, (char, x, y, font, color, align) in enumerate(charlist):
        if char == "----":
            color = color if color else "gray"
            inner_y = y + (font - 0.5) // 2 + padding_y
            draw.line(((0, inner_y), (width, inner_y)), fill=color, width=4)
        else:
            if align == "left":
                start_x = padding_x
            elif align == "nowrap":
                pass
            elif align.isdigit():
                start_x = int(align)
            else:
                for inner_i, inner_y in enumerate(map(lambda x: (x[2]), charlist[i:])):
                    if inner_y != y:
                        inner_index = charlist[i + inner_i - 1]
                        break
                else:
                    inner_index = charlist[-1]
                inner_char = inner_index[0]
                inner_font = inner_index[3]
                inner_x = inner_index[1]
                inner_x += inner_font.getlength(inner_char)
                if align == "right":
                    start_x = width - inner_x - padding_x
                elif align == "center":
                    start_x = (width - inner_x) // 2
                else:
                    start_x = padding_x
            color = color if color else "black"
            draw.text((start_x + x, y + padding_y), char, fill=color, font=font)

    return canvas


ImageList = list[IMG]


def info_splicing(
    info: ImageList,
    BG_path: Path | None = None,
    width: int = 880,
    padding: int = 20,
    spacing: int = 20,
    BG_type: str = "GAUSS",
):
    """
    信息拼接
        info:信息图片列表
        bg_path:背景地址
    """

    height = padding
    for image in info:
        # x = image.size[0] if x < image.size[0] else x
        height += image.size[1]
        height += spacing * 2
    else:
        height = height - spacing + padding

    size = (width + padding * 2, height)
    if BG_path and BG_path.exists():
        bg = Image.open(BG_path).convert("RGB")
        canvas = CropResize(bg, size)
    else:
        canvas = Image.new("RGB", size, "white")
        BG_type = "NONE"

    height = padding

    def colorBG(canvas: IMG, image: IMG):
        colorBG = Image.new("RGBA", (width, image.size[1]), BG_type)
        canvas.paste(colorBG, (20, height), mask=colorBG)
        canvas.paste(image, (20, height), mask=image)

    def blurBG(canvas: IMG, image: IMG):
        box = (20, height, 900, height + image.size[1])
        region = canvas.crop(box)
        blurred_region = region.filter(ImageFilter.GaussianBlur(radius=4))
        canvas.paste(blurred_region, box)
        canvas.paste(image, (20, height), mask=image)

    def noneBG(canvas: IMG, image: IMG):
        canvas.paste(image, (20, height), mask=image)

    funcBG = {"GAUSS": blurBG, "NONE": noneBG}.get(BG_type, colorBG)

    for image in info:
        funcBG(canvas, image)
        height += image.size[1]
        height += spacing * 2
    output = BytesIO()
    canvas.convert("RGB").save(output, format="png")
    return output


def CropResize(img: IMG, size: tuple[int, int]):
    """
    修改图像尺寸
    """

    test_x = img.size[0] / size[0]
    test_y = img.size[1] / size[1]

    if test_x < test_y:
        width = img.size[0]
        height = size[1] * test_x
    else:
        width = size[0] * test_y
        height = img.size[1]

    center = (img.size[0] / 2, img.size[1] / 2)
    output = img.crop(
        (
            int(center[0] - width / 2),
            int(center[1] - height / 2),
            int(center[0] + width / 2),
            int(center[1] + height / 2),
        )
    )
    output = output.resize(size)
    return output

from io import BytesIO
from PIL import Image, ImageDraw
from PIL.Image import Image as IMG

from clovers_leafgame.output import font_manager, format_number


def draw_rank(data: list[tuple[str, int, bytes]]) -> IMG:
    """
    排名信息
    """
    first = data[0][1]
    canvas = Image.new("RGBA", (880, 80 * len(data) + 20))
    draw = ImageDraw.Draw(canvas)
    y = 20
    i = 1
    font = font_manager.font(40)
    circle_mask = Image.new("RGBA", (60, 60), (255, 255, 255, 0))
    ImageDraw.Draw(circle_mask).ellipse(((0, 0), (60, 60)), fill="black")
    for nickname, v, avatar in data:
        if avatar:
            avatar = Image.open(BytesIO(avatar)).resize((60, 60))
            canvas.paste(avatar, (5, y), circle_mask)
        draw.rectangle(((70, y + 10), (70 + int(v / first * 790), y + 50)), fill="#99CCFFCC")
        draw.text((80, y + 10), f"{i}.{nickname} {format_number(v)}", fill=(0, 0, 0), font=font)
        y += 80
        i += 1
    return canvas

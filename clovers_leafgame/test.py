import sys

sys.path.append(r"D:\GIT\clovers")
from linecard import linecard, FontManager

font_manager = font_manager = FontManager(
    "simsun",
    [
        "simsun",
    ],
    (30, 40, 60),
)
info = """[pixel][20]公司 机器人bug研究中心
[pixel][20]结算 [nowrap]
[color][green]0.0[nowrap]
[pixel][400]数量 [nowrap]
[color][green]49
[pixel][20]公司 月儿的白丝袜
[pixel][20]结算 [nowrap]
[color][green]0.0[nowrap]
[pixel][400]数量 [nowrap]
[color][green]1"""
linecard(info, font_manager, 40, width=880, bg_color="white").show()


# def convert_to_fancy_text(text):
#     fancy_text = ""
#     for char in text:
#         if char.isalpha():
#             # 如果是字母，则转换为对应的花体字母
#             fancy_char = chr(ord(char) + ord("Ｌ") - ord("L"))
#         else:
#             # 如果不是字母，则保持原样
#             fancy_char = char
#         fancy_text += fancy_char
#     return fancy_text


# "•ＬＵＣＫＹ ＣＬＯＶＥＲ•"
# "•ＣＡＰＩＴＡＬＩＳＴ•"
# "•ＯＦＦＩＣＩＡＬ•"
# print(len("ＬＵＣＫＹ  ＣＬＯＶＥＲ"))
# print(convert_to_fancy_text("•official tester•".upper()))

import datetime
import os
import random

japanese_month_names = {
    1: "睦月", 2: "如月", 3: "彌生", 4: "卯月", 5: "皐月",
    6: "水無月", 7: "文月", 8: "葉月", 9: "長月", 10: "神無月",
    11: "霜月", 12: "師走"
}


def convert_to_japanese_week(week_num):
    japanese_weeks = {
        0: "日", 1: "月", 2: "火", 3: "水", 4: "木", 5: "金", 6: "土"
    }
    return japanese_weeks.get(week_num, "未知")


def calculate_elements(year):
    year -= 1  # 调整索引，从 0 开始
    sansei = ["日", "月", "星"]
    shiki = ["春", "夏", "秋", "冬"]
    gogyo = ["火", "水", "木", "金", "土"]
    return sansei[year % 3], shiki[year % 4], gogyo[year % 5]

def get_time_as_traditional_chinese_hour(hour, minute):
    chinese_hours = {
        23: "子", 1: "丑", 3: "寅", 5: "卯", 7: "辰", 9: "巳",
        11: "午", 13: "未", 15: "申", 17: "酉", 19: "戌", 21: "亥"
    }

    shichen_hour = hour % 24
    current_shichen_name = ""
    for start_hour, shichen_name in chinese_hours.items():
        if (start_hour <= shichen_hour < start_hour + 2) or (start_hour == 23 and shichen_hour < 1):
            current_shichen_name = shichen_name
            break

    minute_in_shichen = minute % 120

    quarter_index = minute_in_shichen // 15
    if minute_in_shichen < 60:
        shi_segment = "初"
    else:
        shi_segment = "正"
        quarter_index -= 4

    quarter_numbers = ["一", "二", "三", "四"]
    quarter_number_name = quarter_numbers[quarter_index]

    return f"{current_shichen_name}時{shi_segment}{quarter_number_name}刻"


def calculate_fantasy_year_period(year):
    if year < 1885:
        return "幻想郷の遥かな昔"
    else:
        period = min(year - 1885, 200)
        return convert_to_chinese_numerals(period) + "季"


def convert_to_chinese_numerals(num):
    chinese_numerals = {
        0: "零", 1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
        6: "六", 7: "七", 8: "八", 9: "九", 10: "十",
        100: "百", 200: "二百"
    }
    if num <= 10:
        return chinese_numerals[num]
    elif num < 20:
        return "十" + chinese_numerals[num - 10]
    elif num < 100:
        tens = num // 10
        ones = num % 10
        return chinese_numerals[tens] + "十" + (chinese_numerals[ones] if ones != 0 else "")
    elif num <= 200:
        hundreds = num // 100
        remainder = num % 100
        return chinese_numerals[hundreds * 100] + (convert_to_chinese_numerals(remainder) if remainder != 0 else "")
    else:
        return str(num)


def center_text(text, width=40):
    return text.center(width)


def main():
    now = datetime.datetime.now()
    year, month, day, hour, minute = now.year, now.month, now.day, now.hour, now.minute
    weekday = now.weekday()

    sansei_element, shiki_element, gogyo_element = calculate_elements(year)
    japanese_week = convert_to_japanese_week(weekday)
    current_time_traditional = get_time_as_traditional_chinese_hour(hour, minute)
    month_name = japanese_month_names.get(month, "无效月份")
    fantasy_period = calculate_fantasy_year_period(year)

    date_time_str = f"{year}/{month:02}/{day:02} {weekday} {hour:02}:{minute:02}"
    year_element_str_lines = [
        f"{sansei_element}と{shiki_element}と{gogyo_element}の年",
        f"(第{fantasy_period})"
    ]
    month_time_str_lines = [
        f"{month_name}",
        f"{current_time_traditional}",
        f"曜日：{japanese_week}"
    ]

    border_width = 40
    top_border = "┏" + "━" * (border_width - 2) + "┓"
    bottom_border = "┗" + "━" * (border_width - 2) + "┛"

    print(top_border.center(40))
    print(center_text(date_time_str, border_width))
    print(center_text("", border_width))
    for line in year_element_str_lines:
        print(center_text(line, border_width))
    print(center_text("", border_width))
    for line in month_time_str_lines:
        print(center_text(line, border_width))
    print(bottom_border.center(40))


if __name__ == "__main__":
    main()
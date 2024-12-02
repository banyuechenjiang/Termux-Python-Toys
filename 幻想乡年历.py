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
        0: "子", 1: "丑", 2: "寅", 3: "卯", 4: "辰", 5: "巳",
        6: "午", 7: "未", 8: "申", 9: "酉", 10: "戌", 11: "亥"
    }
    chinese_quarters = {
        0: "初", 1: "正", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八"
    }
    k = minute // 15
    hour_str = chinese_hours.get(hour % 12, "未知")
    k_str = chinese_quarters.get(k, "未知")
    return f"{hour_str}時{k_str}刻"

def calculate_fantasy_year_period(year):
    if year < 1885:
        return "幻想郷の遥かな昔"
    else:
        period = min(year - 1885, 200)  # 将季限制在 200 以内
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
    elif num <= 200:  # 处理到 200
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

    try:
        sansei_element, shiki_element, gogyo_element = calculate_elements(year)
        japanese_week = convert_to_japanese_week(weekday)
        current_time_traditional = get_time_as_traditional_chinese_hour(hour, minute)
        month_name = japanese_month_names.get(month, "无效月份")
        fantasy_period = calculate_fantasy_year_period(year)

        # 使用 f-string 格式化输出，并居中对齐
        print(f"{year}/{month:02}/{day:02} {weekday} {hour:02}:{minute:02}".center(40))
        print("".center(40, "─"))  # 使用填充字符创建分隔线
        print(f"{sansei_element}と{shiki_element}と{gogyo_element}の年".center(40))
        print(f"(第{fantasy_period})".center(40))
        print("".center(40, "─"))
        print(f"{month_name}".center(40))
        print(f"{current_time_traditional}".center(40))
        print(f"曜日：{japanese_week}".center(40))

    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
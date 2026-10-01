import re
import unicodedata

from rest_framework.exceptions import ValidationError


def category_name(value):
    value = " ".join(unicodedata.normalize("NFKC", value).split())
    if not value or len(value) > 100 or len(value.casefold()) > 100:
        raise ValidationError("分类名称必填，规范化后最多 100 字符。")
    return value


def normalize_isbn(value):
    value = re.sub(r"[\s-]", "", value).upper()
    if re.fullmatch(r"[0-9]{9}[0-9X]", value):
        digits = [int(char) if char != "X" else 10 for char in value]
        if (
            sum((10 - index) * digit for index, digit in enumerate(digits))
            % 11
        ):
            raise ValidationError("ISBN-10 校验位错误。")
        prefix = "978" + value[:9]
        check = (
            10
            - sum(
                int(char) * (1 if index % 2 == 0 else 3)
                for index, char in enumerate(prefix)
            )
            % 10
        ) % 10
        return prefix + str(check)
    if re.fullmatch(r"(?:978|979)[0-9]{10}", value):
        if (
            sum(
                int(char) * (1 if index % 2 == 0 else 3)
                for index, char in enumerate(value)
            )
            % 10
            == 0
        ):
            return value
        raise ValidationError("ISBN-13 校验位错误。")
    raise ValidationError("请输入合法 ISBN-10 或 978/979 开头的 ISBN-13。")

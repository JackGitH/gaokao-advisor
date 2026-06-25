"""
Canonical school tier normalization.

The app stores a single primary school type for display:
985 > 211 > 双一流 > 普通本科 > 高职专科.
"""

PROJECT_985_SCHOOLS = {
    "清华大学",
    "北京大学",
    "复旦大学",
    "上海交通大学",
    "浙江大学",
    "中国科学技术大学",
    "南京大学",
    "中国人民大学",
    "北京航空航天大学",
    "同济大学",
    "武汉大学",
    "华中科技大学",
    "西安交通大学",
    "哈尔滨工业大学",
    "中山大学",
    "东南大学",
    "天津大学",
    "北京理工大学",
    "厦门大学",
    "四川大学",
    "南开大学",
    "电子科技大学",
    "北京师范大学",
    "华南理工大学",
    "大连理工大学",
    "吉林大学",
    "湖南大学",
    "重庆大学",
    "山东大学",
    "中国海洋大学",
    "山东大学威海分校",
    "兰州大学",
    "东北大学",
    "中国农业大学",
    "西北农林科技大学",
}

PROJECT_211_ONLY_SCHOOLS = {
    "北京邮电大学",
    "上海财经大学",
    "中央财经大学",
    "对外经济贸易大学",
    "西安电子科技大学",
    "南京航空航天大学",
    "南京理工大学",
    "北京交通大学",
    "华东理工大学",
    "河海大学",
    "苏州大学",
    "中南财经政法大学",
    "武汉理工大学",
    "西南财经大学",
    "华北电力大学",
    "中国政法大学",
    "北京科技大学",
    "北京外国语大学",
    "上海外国语大学",
    "暨南大学",
    "中国地质大学(武汉)",
    "中国石油大学(华东)",
    "中国矿业大学",
    "长安大学",
    "合肥工业大学",
    "福州大学",
    "南昌大学",
    "郑州大学",
    "哈尔滨工程大学",
    "太原理工大学",
    "海南大学",
    "上海大学",
    "湖南师范大学",
    "华南师范大学",
    "陕西师范大学",
    "东北师范大学",
    "西北大学",
    "北京化工大学",
    "中国传媒大学",
    "北京中医药大学",
    "南京师范大学",
    "江南大学",
    "西南大学",
    "安徽大学",
    "辽宁大学",
}

# Second-round Double First-Class schools that are not 985/211.
DOUBLE_FIRST_CLASS_ONLY_SCHOOLS = {
    "北京协和医学院",
    "首都师范大学",
    "外交学院",
    "中国人民公安大学",
    "中国音乐学院",
    "中央美术学院",
    "中央戏剧学院",
    "中国科学院大学",
    "天津工业大学",
    "天津中医药大学",
    "山西大学",
    "南京医科大学",
    "南京中医药大学",
    "南京邮电大学",
    "南京信息工程大学",
    "南京林业大学",
    "上海海洋大学",
    "上海中医药大学",
    "上海体育大学",
    "上海音乐学院",
    "上海科技大学",
    "中国美术学院",
    "宁波大学",
    "南方科技大学",
    "广州医科大学",
    "广州中医药大学",
    "华南农业大学",
    "成都理工大学",
    "成都中医药大学",
    "西南石油大学",
    "湘潭大学",
}

PROJECT_VOCATIONAL_SCHOOLS = {
    "山东商业职业技术学院",
    "淄博职业学院",
    "日照职业技术学院",
    "山东职业学院",
    "青岛职业技术学院",
    "威海职业学院",
    "烟台职业学院",
    "潍坊职业学院",
    "济南职业学院",
    "山东科技职业学院",
    "山东畜牧兽医职业学院",
    "山东交通职业学院",
}

DOUBLE_FIRST_CLASS_SCHOOLS = (
    PROJECT_985_SCHOOLS
    | PROJECT_211_ONLY_SCHOOLS
    | DOUBLE_FIRST_CLASS_ONLY_SCHOOLS
)

PRIMARY_TYPE_BY_SCHOOL = {
    **{name: "985" for name in PROJECT_985_SCHOOLS},
    **{name: "211" for name in PROJECT_211_ONLY_SCHOOLS},
    **{name: "双一流" for name in DOUBLE_FIRST_CLASS_ONLY_SCHOOLS},
    **{name: "高职专科" for name in PROJECT_VOCATIONAL_SCHOOLS},
    "山东师范大学": "普通本科",
    "青岛大学": "普通本科",
}


def _split_features(features: str = None) -> list:
    return [item.strip() for item in (features or "").split(",") if item.strip()]


def normalize_features(name: str, features: str = None) -> str:
    """Normalize outdated or incorrect feature labels."""
    parts = []
    for item in _split_features(features):
        if item in ("双一流A类", "双一流B类"):
            item = "双一流"
        if item == "双一流" and name not in DOUBLE_FIRST_CLASS_SCHOOLS:
            continue
        if item not in parts:
            parts.append(item)

    if name in DOUBLE_FIRST_CLASS_SCHOOLS and "双一流" not in parts:
        parts.append("双一流")

    return ",".join(parts) if parts else None


def normalize_school_level_fields(
    name: str,
    school_type: str = None,
    features: str = None,
) -> tuple:
    """Return canonical (type, features) for a school row."""
    normalized_type = PRIMARY_TYPE_BY_SCHOOL.get(name, school_type)
    normalized_features = normalize_features(name, features)
    return normalized_type, normalized_features


def is_double_first_class(name: str, school_type: str = None, features: str = None) -> bool:
    if name in PRIMARY_TYPE_BY_SCHOOL:
        return name in DOUBLE_FIRST_CLASS_SCHOOLS

    return (
        name in DOUBLE_FIRST_CLASS_SCHOOLS
        or school_type in ("985", "211", "双一流")
        or "双一流" in _split_features(features)
    )

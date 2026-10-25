from __future__ import annotations

OBSERVATION_OPTIONS = [
    {"value": "OFTEN", "label": "经常观察到"},
    {"value": "SOMETIMES", "label": "偶尔观察到"},
    {"value": "NOT_SEEN_THIS_TIME", "label": "本次未观察到"},
    {"value": "UNABLE_TO_JUDGE", "label": "无法判断"},
    {"value": "NOT_OBSERVED", "label": "未观察"},
]

OBSERVATION_DIMENSIONS = [
    {
        "key": "social_interaction",
        "label": "社交互动",
        "items": [
            {"key": "initiates_interaction", "label": "主动发起与他人的互动"},
            {"key": "responds_to_interaction", "label": "在他人发起互动时作出回应"},
        ],
    },
    {
        "key": "communication",
        "label": "语言与沟通",
        "items": [
            {"key": "expresses_needs", "label": "使用语言、动作或其他方式表达需求"},
            {"key": "shares_information", "label": "主动向他人分享信息或感受"},
        ],
    },
    {
        "key": "response_to_calling",
        "label": "对他人呼唤的反应",
        "items": [
            {"key": "responds_to_name", "label": "在环境允许时对称呼或呼唤作出反应"},
            {"key": "shifts_attention", "label": "根据他人提示调整注意方向"},
        ],
    },
    {
        "key": "shared_activity",
        "label": "共同活动参与情况",
        "items": [
            {"key": "joins_shared_activity", "label": "参与与他人共同进行的活动"},
            {"key": "takes_turns", "label": "在适合的活动中进行轮流或等待"},
        ],
    },
    {
        "key": "interests_and_play",
        "label": "兴趣与游戏表现",
        "items": [
            {"key": "explores_materials", "label": "主动探索玩具、材料或活动内容"},
            {"key": "varies_play", "label": "在游戏中使用不同方式或内容"},
        ],
    },
    {
        "key": "daily_routines",
        "label": "日常行为习惯",
        "items": [
            {"key": "follows_routine", "label": "在提示下参与日常流程"},
            {"key": "adapts_to_change", "label": "面对活动或流程变化时作出调整"},
        ],
    },
]

OBSERVATION_SCENES = ["家庭日常", "游戏活动", "学习活动", "用餐时段", "外出活动", "其他"]
OBSERVER_ROLES = ["家长", "其他监护人", "教师", "专业人员", "其他观察者"]

ITEMS = {
    item["key"]: {"label": item["label"], "dimension_key": dimension["key"], "dimension_label": dimension["label"]}
    for dimension in OBSERVATION_DIMENSIONS
    for item in dimension["items"]
}
OPTION_LABELS = {item["value"]: item["label"] for item in OBSERVATION_OPTIONS}


def form_definition() -> dict:
    return {
        "dimensions": OBSERVATION_DIMENSIONS,
        "options": OBSERVATION_OPTIONS,
        "scenes": OBSERVATION_SCENES,
        "observer_roles": OBSERVER_ROLES,
        "disclaimer": "本记录用于日常行为观察与信息整理，不构成医学诊断或标准化筛查结果。如对儿童发育情况存在疑虑，请咨询儿科或儿童发育行为专业人员。",
    }

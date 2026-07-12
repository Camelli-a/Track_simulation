from __future__ import annotations


ALARM_MESSAGE_TRANSLATIONS = {
    "Train is close to MA limit": "列车接近移动授权边界",
    "Signal timeout detected": "信号系统响应超时",
    "Power voltage drop": "接触网电压下降",
    "Communication latency high": "通信延迟过高",
    "Mock warning: check voltage or section occupancy": "模拟告警：请检查网压或区段占用状态",
    "Train overspeed, emergency brake triggered": "列车超速，已触发紧急制动",
    "Train exceeded MA limit, emergency brake triggered": "列车越过移动授权边界，已触发紧急制动",
    "Power fault, emergency brake triggered": "供电故障，已触发紧急制动",
    "Communication lost, emergency brake triggered": "通信中断，已触发紧急制动",
    "Unknown alarm": "未知告警",
}


ALARM_LEVEL_LABELS = {
    "info": "信息",
    "warning": "警告",
    "critical": "严重",
}


ALARM_SOURCE_LABELS = {
    "ATP": "ATP 安全防护",
    "ATO": "ATO 自动驾驶",
    "SIGNAL": "信号系统",
    "POWER": "供电系统",
    "COMM": "通信系统",
    "BACKEND": "后端服务",
}


def translate_alarm_message(message: str | None) -> str:
    if not message:
        return ALARM_MESSAGE_TRANSLATIONS["Unknown alarm"]
    return ALARM_MESSAGE_TRANSLATIONS.get(message, message)


def alarm_level_label(level: str | None) -> str:
    return ALARM_LEVEL_LABELS.get(level or "", level or "未知")


def alarm_source_label(source: str | None) -> str:
    return ALARM_SOURCE_LABELS.get(source or "", source or "未知来源")

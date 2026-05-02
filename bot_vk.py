"""VK Bots Long Poll: портфолио, FAQ, контакт поддержки."""

from __future__ import annotations

import logging
import os
import random
import re
import threading
from typing import Any

import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

log = logging.getLogger(__name__)

PORTFOLIO_TEXT = """Примеры работ

• Канал/группа ВК — оформление, посты, рубрики
• Чат-бот для приёма заявок и ответов на частые вопросы
• Интеграция с CRM / Google Таблицами (по запросу)
• Техническая поддержка и доработки существующих ботов

Если нужно что-то из списка или своё — напишите в поддержку."""

FAQ_ITEMS: list[tuple[str, str]] = [
    (
        "Сроки",
        "Сроки зависят от задачи: простой бот — от нескольких дней, проекты с интеграциями — обсуждаем отдельно. Напишите, что нужно — оценим.",
    ),
    (
        "Стоимость",
        "Цена рассчитывается по ТЗ: сложность сценариев, интеграции, срок. Можем начать с небольшого пилота и развивать дальше.",
    ),
    (
        "Как заказать",
        "Напишите в поддержку кратко: цель бота, желаемые сценарии, сроки. Пришлите ссылку на группу/сайт, если есть.",
    ),
    (
        "Гарантии",
        "После сдачи — согласованный период правок по договорённым сценариям. Критические ошибки исправляем в приоритете.",
    ),
]

SUPPORT_BODY = """Поддержка

Напишите нам в сообщения сообщества — разберём вопрос и ответим.
Обычно отвечаем в течение рабочего дня.

Ссылка для переписки: {url}

Можно ответить прямо в этом чате с тегом #поддержка — так заявка не потеряется."""


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _random_id() -> int:
    return random.randint(0, 2**31 - 1)


def _main_menu_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Примеры работ", color=VkKeyboardColor.PRIMARY)
    kb.add_button("Частые вопросы", color=VkKeyboardColor.PRIMARY)
    kb.new_line()
    kb.add_button("Поддержка", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def _faq_menu_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    for i, (title, _) in enumerate(FAQ_ITEMS):
        kb.add_button(f"❓ {title}", color=VkKeyboardColor.PRIMARY)
        if i % 2 == 1:
            kb.new_line()
    if len(FAQ_ITEMS) % 2 == 1:
        kb.new_line()
    kb.add_button("⬅ В главное меню", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def _support_url(group_id: int) -> str:
    custom = os.environ.get("SUPPORT_URL", "").strip()
    if custom:
        return custom
    gid = abs(group_id) if group_id < 0 else group_id
    return f"https://vk.com/im?sel=-{gid}"


def _send(
    vk: Any,
    peer_id: int,
    message: str,
    keyboard: str | None = None,
) -> None:
    params: dict[str, Any] = {
        "peer_id": peer_id,
        "message": message,
        "random_id": _random_id(),
    }
    if keyboard is not None:
        params["keyboard"] = keyboard
    vk.messages.send(**params)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _faq_answer_by_button_payload(text: str) -> str | None:
    stripped = text.strip()
    for title, answer in FAQ_ITEMS:
        if stripped == f"❓ {title}" or stripped == title:
            return answer
    return None


def _is_portfolio_request(text_raw: str, text_norm: str) -> bool:
    if text_raw.strip() == "Примеры работ":
        return True
    return bool(re.search(r"\bпример[ыа]?\s+работ", text_norm)) or text_norm in (
        "портфолио",
        "работы",
        "что вы делали",
    )


def _is_faq_menu_request(text_raw: str, text_norm: str) -> bool:
    if text_raw.strip() == "Частые вопросы":
        return True
    return text_norm in ("faq", "частые вопросы", "вопросы") or text_norm.startswith(
        "частые вопросы "
    )


def _is_support_request(text_raw: str, text_norm: str) -> bool:
    if text_raw.strip() == "Поддержка":
        return True
    if "#поддержка" in text_norm:
        return True
    return bool(
        re.search(
            r"\b(в\s+)?поддержк[ауе]\b|\bподдержать\b|\bнаписать\s+в\s+поддержку\b",
            text_norm,
        )
    )


def _is_main_menu_request(text_norm: str) -> bool:
    return bool(
        re.search(
            r"\bглавн(ое|ая)?\s+меню\b|\bв\s+меню\b|\bназад\b",
            text_norm,
        )
    )


def run_bot() -> None:
    token = os.environ.get("VK_GROUP_TOKEN", "").strip()
    raw_gid = _env_int("VK_GROUP_ID")
    if not token or raw_gid is None:
        log.warning(
            "VK бот не запущен: задайте VK_GROUP_TOKEN и VK_GROUP_ID в переменных окружения."
        )
        return

    group_id = raw_gid
    support_url = _support_url(group_id)

    vk_session = vk_api.VkApi(token=token)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id=group_id)

    log.info("VK Bots Long Poll запущен для group_id=%s", group_id)

    for event in longpoll.listen():
        if event.type != VkBotEventType.MESSAGE_NEW:
            continue

        msg = event.message
        if not msg:
            continue
        peer_id = msg.get("peer_id")
        if peer_id is None:
            continue

        text_raw = msg.get("text") or ""
        text_norm = _normalize_text(text_raw)

        direct = _faq_answer_by_button_payload(text_raw)
        if direct:
            _send(vk, peer_id, direct, keyboard=_faq_menu_keyboard())
            continue

        if _is_portfolio_request(text_raw, text_norm):
            _send(vk, peer_id, PORTFOLIO_TEXT, keyboard=_main_menu_keyboard())
        elif _is_faq_menu_request(text_raw, text_norm):
            lines = [f"• {t[0]}" for t in FAQ_ITEMS]
            _send(
                vk,
                peer_id,
                "Частые вопросы\n\n"
                + "\n".join(lines)
                + "\n\nВыберите тему кнопкой ниже или вернитесь в меню.",
                keyboard=_faq_menu_keyboard(),
            )
        elif _is_support_request(text_raw, text_norm):
            _send(
                vk,
                peer_id,
                SUPPORT_BODY.format(url=support_url),
                keyboard=_main_menu_keyboard(),
            )
        elif _is_main_menu_request(text_norm):
            _send(
                vk,
                peer_id,
                "Главное меню. Выберите раздел:",
                keyboard=_main_menu_keyboard(),
            )
        elif text_norm in ("старт", "/start", "начать", "привет", "hi", "hello", "меню"):
            _send(
                vk,
                peer_id,
                "Привет! Я помогу с примерами работ, ответами на частые вопросы и контактом поддержки.\n\n"
                "Выберите раздел кнопкой ниже.",
                keyboard=_main_menu_keyboard(),
            )
        else:
            _send(
                vk,
                peer_id,
                "Выберите раздел в меню или напишите: примеры работ, частые вопросы, поддержка.",
                keyboard=_main_menu_keyboard(),
            )


def start_bot_thread() -> threading.Thread | None:
    token = os.environ.get("VK_GROUP_TOKEN", "").strip()
    if not token or _env_int("VK_GROUP_ID") is None:
        return None

    t = threading.Thread(target=run_bot, name="vk-bot-longpoll", daemon=True)
    t.start()
    return t

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

• telega_stalker — Telegram-игра в духе S.T.A.L.K.E.R. (Python, aiogram 3): регистрация и персонаж, выбор группировки, инвентарь и ручная экипировка, задания с учётом снаряжения и амуниции, война за точки и рейды, динамические события Зоны, расширенная экономика (склад, аукцион, контрабанда), отрядные рейды, поиск артефактов с детекторами, оплата Telegram Stars, карточка профиля и визуальные аватары по уровню снаряги, деплой с постоянной БД (Railway и т.п.).

• vk-prof-bot — бот ВКонтакте на Python: крупный сценарий в одном проекте, библиотека психодиагностических опросников (Kettell 16PF, Голланд RIASEC, DDO, EN и др. в JSON), сопутствующие данные и ассеты, сценарии прохождения тестов; готовность к выкладке (Procfile, Railway, nixpacks).

• nail-salon-bot — Telegram-бот для ногтевого/салонного сервиса (Python, aiogram 3): SQLite (aiosqlite), модули меню, записи (booking), чата, админки, планировщик напоминаний (APScheduler), интеграция OpenAI, выгрузки через openpyxl, слоты и расписание; структура handlers / keyboards / services / database.

Нужно что-то похожее или под ключ — напишите в поддержку."""

FAQ_ITEMS: list[tuple[str, str]] = [
    (
        "Сроки",
        "Сроки зависят от объёма: сценарий и кнопки без внешних сервисов — обычно от нескольких дней; запись, оплаты, CRM, отчёты, сложные интеграции — дольше. Точнее скажу после краткого ТЗ.",
    ),
    (
        "Стоимость",
        "Считаю по сценариям, интеграциям и сопровождению. Можно начать с MVP (минимум функций) и наращивать. Бюджет согласуем до старта работ.",
    ),
    (
        "Как заказать",
        "Напишите в поддержку: зачем бот, ВК или Telegram, примеры сценариев, срок, ссылка на группу/сайт. Чем конкретнее — тем быстрее смета.",
    ),
    (
        "Гарантии",
        "После сдачи — согласованные итерации правок по принятому ТЗ. Критичные сбои в работе бота устраняю в приоритете. Детали фиксируем при сдаче.",
    ),
    (
        "ВК или Telegram",
        "ВК — удобно, если аудитория в сообществе. Telegram — сильные боты, Mini Apps, гибкие сценарии, Stars. Могу сверить с вашей воронкой и подсказать вариант.",
    ),
    (
        "Хостинг",
        "Боту нужен постоянно работающий сервер (Railway, Render, VPS и т.д.). Помогу с деплоем и переменными окружения. База и файлы — на диске с бэкапом, чтобы не терять записи.",
    ),
    (
        "Данные и доступы",
        "Нужны токены бота и права в сообществе/боте. Доступы храните у себя; в код не вкладываю секреты — только через env. Персональные данные клиентов настраиваем под вашу политику.",
    ),
    (
        "Оплата в боте",
        "В Telegram часто Stars или внешняя касса по API. В ВК — платежи по правилам платформы. Подключение зависит от страны и провайдера — обсуждаем до разработки.",
    ),
    (
        "После запуска",
        "Можно договориться о сопровождении: мониторинг, мелкие правки, новые сценарии. Разовые доработки — по оценке после описания задачи.",
    ),
    (
        "Запись и салон",
        "Типичный набор: услуги и мастера, свободные слоты, напоминания, перенос/отмена, админка. Интеграции с таблицами или CRM — по необходимости.",
    ),
    (
        "Что в ТЗ указать",
        "Платформа, примеры диалогов, список кнопок/разделов, нужна ли запись/оплата/выгрузки, язык, роли (админ/клиент). Чем полнее черновик — тем точнее срок и цена.",
    ),
]

SUPPORT_BODY = """Поддержка

Напишите нам в сообщения сообщества — разберём вопрос и ответим.
Обычно отвечаем в течение рабочего дня.

Ссылка для переписки: {url}

Можно ответить прямо в этом чате с тегом #поддержка — так заявка не потеряется."""

GREETING_TEXT = """Здравствуйте!

Я помогаю с разработкой чат-ботов для ВКонтакте и Telegram: покажу портфолио, отвечу на частые вопросы или подскажу, как связаться с поддержкой.

Выберите действие кнопкой ниже."""


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
    kb.add_button("Портфолио", color=VkKeyboardColor.PRIMARY)
    kb.add_button("FAQ", color=VkKeyboardColor.PRIMARY)
    kb.new_line()
    kb.add_button("Меню", color=VkKeyboardColor.SECONDARY)
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
    kb.add_button("⬅ Меню", color=VkKeyboardColor.SECONDARY)
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
    s = text_raw.strip()
    if s in ("Портфолио", "Примеры работ"):
        return True
    return bool(re.search(r"\bпример[ыа]?\s+работ", text_norm)) or text_norm in (
        "портфолио",
        "работы",
        "что вы делали",
    )


def _is_faq_menu_request(text_raw: str, text_norm: str) -> bool:
    s = text_raw.strip()
    if s in ("FAQ", "Частые вопросы"):
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


def _is_main_menu_request(text_raw: str, text_norm: str) -> bool:
    s = text_raw.strip()
    if s in ("⬅ Меню", "⬅ В главное меню"):
        return True
    return bool(
        re.search(
            r"\bглавн(ое|ая)?\s+меню\b|\bв\s+меню\b|\bназад\b",
            text_norm,
        )
    )


def _should_show_greeting(text_raw: str, text_norm: str) -> bool:
    s = text_raw.strip()
    if s in ("Меню", "⬅ Меню", "⬅ В главное меню"):
        return True
    if text_norm in ("старт", "/start", "начать", "привет", "hi", "hello", "меню"):
        return True
    return _is_main_menu_request(text_raw, text_norm)


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
        if event.type == VkBotEventType.MESSAGE_ALLOW:
            obj = event.object
            uid = obj.get("user_id") if obj else None
            if uid:
                _send(vk, uid, GREETING_TEXT, keyboard=_main_menu_keyboard())
            continue

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
                + "\n\nВыберите тему кнопкой ниже или нажмите «Меню».",
                keyboard=_faq_menu_keyboard(),
            )
        elif _is_support_request(text_raw, text_norm):
            _send(
                vk,
                peer_id,
                SUPPORT_BODY.format(url=support_url),
                keyboard=_main_menu_keyboard(),
            )
        elif _should_show_greeting(text_raw, text_norm):
            _send(vk, peer_id, GREETING_TEXT, keyboard=_main_menu_keyboard())
        else:
            _send(
                vk,
                peer_id,
                "Выберите действие кнопкой: Портфолио, FAQ, Меню или Поддержка.",
                keyboard=_main_menu_keyboard(),
            )


def start_bot_thread() -> threading.Thread | None:
    token = os.environ.get("VK_GROUP_TOKEN", "").strip()
    if not token or _env_int("VK_GROUP_ID") is None:
        return None

    t = threading.Thread(target=run_bot, name="vk-bot-longpoll", daemon=True)
    t.start()
    return t

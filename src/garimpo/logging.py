"""structlog setup."""

from __future__ import annotations

import logging

import structlog

# Bibliotecas que falam demais no nível INFO. O Telethon narra cada handshake
# e cada "Got difference for channel", e como isso vai para o logger raiz sai
# em stderr: 146 das 170 linhas do err log eram ruído dele, enterrando o que
# de fato importa. Em WARNING sobra o que você quer ver — FloodWait, erro de
# conexão, desautorização.
_RUIDOSAS = ("telethon", "asyncio", "httpx", "httpcore", "hpack")


def quiet_libraries(level: int = logging.WARNING) -> None:
    for nome in _RUIDOSAS:
        logging.getLogger(nome).setLevel(level)


def configure_logging(*, level: str = "INFO", fmt: str = "console") -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    # Em DEBUG o usuário pediu para ver tudo, inclusive o handshake. Restaurar
    # para NOTSET em vez de só pular o silenciamento: o nível fica no objeto
    # logger, então uma chamada anterior continuaria valendo.
    quiet_libraries(logging.NOTSET if level.upper() == "DEBUG" else logging.WARNING)
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    if fmt == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)

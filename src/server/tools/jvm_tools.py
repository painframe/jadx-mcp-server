"""Format-aware inspection of JVM archives without Android-only assumptions."""

from typing import Literal

from src.server.config import get_from_jadx

JvmSection = Literal['manifest', 'services', 'entry-points', 'dependencies', 'properties', 'packages']


async def get_jvm_info(section: JvmSection) -> dict:
    """Read archive metadata; dependency summaries reflect bytecode, not runtime resolution."""
    return await get_from_jadx('jvm-info', {'section': section})

# Decorators:
# - retry: بيعيد المحاولة إذا فشل استدعاء الـ LLM
# - timed: بيحسب قديش أخد الاستدعاء من وقت
#
# 📝 نوتات تعلّمتها:
# - الـ decorator = function بتاخد function وبترجّع function جديدة "ملفوفة".
#     @timed فوق f  ==  f = timed(f)        <- الـ @ مجرد اختصار
# - decorator بياخد إعدادات (retry) بدو 3 طبقات:
#     @retry(attempts=3)  ==  f = retry(attempts=3)(f)
#     retry(إعدادات) -> decorator(func) -> wrapper(*args, **kwargs)
#     ولهيك حتى مع الافتراضي لازم أقواس: @retry()
# - *args, **kwargs: استقبل أي arguments -> الـ decorator بيشتغل على أي function.
# - return wrapper بدون أقواس: منرجّع الـ function نفسها، مش نتيجتها.
# - functools.wraps: بيحفظ اسم الأصلية. جربت شلته -> صار الاسم "wrapper".
#     مهم لما نركّب decorators فوق بعض، وإلا الـ logs بتصير كلها "wrapper failed".
# - try/finally: الـ finally بتنفّذ دايماً، نجحت الـ function أو رمت خطأ.
#     بدونها، لو صار خطأ بايثون بيقفز لبره وما منسجّل الوقت.
# - retry:
#     - attempts = عدد المحاولات بالمجموع، delay * attempt = انتظار بيكبر (1، 2، 3 ثواني...)
#     - exceptions=(Exception,) -> tuple، الفاصلة ضرورية.
#     - raise لحالها = ارمي نفس الخطأ اللي مسكناه (بآخر محاولة منستسلم).
#     - جربت attempts=3 على function بتفشل مرتين -> نجحت بالتالتة ✅
#     - جربت attempts=2 -> warning وحدة بس، وبعدين ValueError طلع للي استدعى 💥
# - logging بدل print: getLogger(__name__) بيقول من وين إجت الرسالة. info للعادي، warning للمشاكل.
# - async def = function ممكن تستنى بدون ما توقف البرنامج، await = استنى النتيجة هون.
import asyncio
import functools
import logging
import time

logger = logging.getLogger(__name__)


def timed(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return await func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            logger.info("%s took %.2fs", func.__qualname__, elapsed)

    return wrapper


def retry(attempts=3, delay=1.0, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == attempts:
                        raise
                    logger.warning(
                        "%s failed (attempt %d/%d): %s",
                        func.__qualname__,
                        attempt,
                        attempts,
                        exc,
                    )
                    await asyncio.sleep(delay * attempt)

        return wrapper

    return decorator

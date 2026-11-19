# اختبارات الـ decorators: retry بيعيد المحاولة صح، و timed ما بيغيّر القيمة الراجعة.
#
# 📝 نوتات تعلّمتها:
# - pytest بيلاقي لحاله الـ functions اللي بتبدأ بـ test_ وبيشغّلها. الاسم لازم يوصف شو منختبر.
# - assert = فحص بس. بكود البرنامج ما منعتمد عليها للحماية، لأن python -O بيمسحها.
#     الحماية بالبرنامج = raise / Pydantic. والـ assert بالاختبار بتتأكد إنه الحماية شغالة.
# - @pytest.mark.asyncio: لازم لكل اختبار async، pytest لحاله ما بيعرف يشغّل async def.
#     ⚠️ غلطة صارت معي: كتبت asynico -> "Unknown mark - is this a typo?" والاختبار فشل.
#     الدرس: اقرئي الـ warnings summary بالآخر، pytest غالباً بيقلك الغلط حرفياً ورقم السطر.
# - nonlocal: متغير من الـ function اللي حواليّ (global: متغير من الملف كله).
# - pytest.raises(X): الاختبار بينجح إذا طلع الخطأ X، وبيفشل إذا ما طلع.
# - assert calls == 2 بعد الـ with: raises لحالها بتتأكد إنه فشل بس،
#     وما بتتأكد إنه جرّب العدد الصح (مش مرة وحدة بدون retry، ومش أكتر من attempts).
# - delay=0 بالاختبارات: الاختبار لازم يكون سريع.
import pytest

from repolens.core.decorators import retry, timed


@pytest.mark.asyncio
async def test_retry_succeeds_after_failures():
    calls = 0

    @retry(attempts=3, delay=0)
    async def flaky():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("boom")
        return "ok"

    assert await flaky() == "ok"
    assert calls == 3


@pytest.mark.asyncio
async def test_retry_gives_up_after_last_attempt():
    calls = 0

    @retry(attempts=2, delay=0)
    async def always_fails():
        nonlocal calls
        calls += 1
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await always_fails()
    assert calls == 2


@pytest.mark.asyncio
async def test_timed_keeps_return_value_and_name():
    @timed
    async def add(a, b):
        return a + b

    assert await add(2, 3) == 5
    assert add.__name__ == "add"

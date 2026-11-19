# evaluators: بيجمع كل أنواع التقييم بقائمة وحدة عشان الـ pipeline يشغّلهم كلهم.
from repolens.evaluators.base import BaseEvaluator
from repolens.evaluators.commits import CommitsEvaluator
from repolens.evaluators.readme import ReadmeEvaluator
from repolens.evaluators.structure import StructureEvaluator
from repolens.evaluators.tests import TestsEvaluator

EVALUATOR_CLASSES: list[type[BaseEvaluator]] = [
    ReadmeEvaluator,
    StructureEvaluator,
    TestsEvaluator,
    CommitsEvaluator,
]


def default_evaluators() -> list[BaseEvaluator]:
    return [cls() for cls in EVALUATOR_CLASSES]


__all__ = [
    "BaseEvaluator",
    "CommitsEvaluator",
    "ReadmeEvaluator",
    "StructureEvaluator",
    "TestsEvaluator",
    "default_evaluators",
]

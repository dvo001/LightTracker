from dataclasses import dataclass
from typing import List


@dataclass
class RangeSample:
    src: str
    dst: str
    rssi: float
    dist_mm: int


class RangeCache:
    def __init__(self):
        self._samples: List[RangeSample] = []

    def add(self, sample: RangeSample):
        self._samples.append(sample)
# Range cache

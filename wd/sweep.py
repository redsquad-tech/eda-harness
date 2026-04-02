from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Generic, Iterable, TypeVar
import csv

import hdl21 as h
import vlsirtools.spice as vtsp
from hdl21.sim import Sim

X = TypeVar("X")  # sweep value type
R = TypeVar("R")  # extracted result type


@dataclass
class SweepPointResult(Generic[X]):
    value: X
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class SweepConfig:
    model_lib: str
    model_section: str = "tt"
    rundir: str = "./scratch"
    simulator: Any = None
    result_format: Any = None
    reltol: float = 1e-5

    def make_sim_options(self) -> vtsp.SimOptions:
        simulator = self.simulator or vtsp.SupportedSimulators.NGSPICE
        result_format = self.result_format or vtsp.ResultFormat.SIM_DATA
        Path(self.rundir).mkdir(parents=True, exist_ok=True)
        return vtsp.SimOptions(
            simulator=simulator,
            fmt=result_format,
            rundir=self.rundir,
        )


class SweepRunner(Generic[X]):
    """
    Универсальный sweep runner поверх Hdl21 + vlsirtools.

    tb_factory(value) -> h.Module
        Создает testbench для конкретного значения sweep.

    sim_builder(sim)
        Добавляет анализы в Sim. Например s.op(name="op") или s.tran(...)

    extract_fn(result, value) -> dict
        Вытаскивает метрики из результата симуляции.
    """

    def __init__(
        self,
        config: SweepConfig,
        tb_factory: Callable[[X], h.Module],
        sim_builder: Callable[[Sim], None],
        extract_fn: Callable[[Any, X], dict[str, Any]],
    ) -> None:
        self.config = config
        self.tb_factory = tb_factory
        self.sim_builder = sim_builder
        self.extract_fn = extract_fn

    def run_one(self, value: X) -> SweepPointResult[X]:
        try:
            tb = self.tb_factory(value)

            sim = Sim(tb=tb)
            sim.lib(path=self.config.model_lib, section=self.config.model_section)
            sim.options(name="reltol", value=self.config.reltol)

            self.sim_builder(sim)

            opts = self.config.make_sim_options()
            raw_result = sim.run(opts)

            data = self.extract_fn(raw_result, value)
            return SweepPointResult(value=value, ok=True, data=data)

        except Exception as e:
            return SweepPointResult(value=value, ok=False, error=str(e))

    def run_many(self, values: Iterable[X]) -> list[SweepPointResult[X]]:
        return [self.run_one(v) for v in values]

    @staticmethod
    def save_csv(
        results: list[SweepPointResult[Any]],
        path: str | Path,
    ) -> None:
        path = Path(path)

        rows: list[dict[str, Any]] = []
        for r in results:
            row = {
                "value": r.value,
                "ok": r.ok,
                "error": r.error,
            }
            if r.data:
                row.update(r.data)
            rows.append(row)

        fieldnames: list[str] = []
        seen = set()
        for row in rows:
            for k in row.keys():
                if k not in seen:
                    seen.add(k)
                    fieldnames.append(k)

        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
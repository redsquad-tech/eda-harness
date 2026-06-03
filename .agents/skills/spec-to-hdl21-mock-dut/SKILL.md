---
name: spec-to-hdl21-mock-dut
description: Используй этот skill чтобы создать HDL21 mock DUT и сгенерированный SPICE mock netlist по specification, verification_plan.md и optional SPICE/HDL21 DUT netlist.
---

# Skill: Spec to HDL21 Mock DUT

## Назначение

Создай mock DUT для разработки и sanity-check testbench-ей.

Mock DUT не является реальной реализацией устройства. Он должен совпадать с публичным DUT contract из `verification_plan.md` и в упрощённом виде воспроизводить внешнее поведение, нужное для измерений из Acceptance Test Matrix.

## Входные данные

* Specification.
* `verification_plan.md`.
* Optional DUT netlist: SPICE или HDL21, только для уточнения top name, public ports и pin order.

## Выход

Создай или обнови:

```text
mock_device.py
mock_device.sp
```

`mock_device.sp` должен генерироваться из `mock_device.py`. Generated SPICE не редактируй вручную.

## Главные правила

* DUT contract важнее внутренней реализации mock-а.
* Generated SPICE должен содержать `.subckt`/top wrapper с тем же именем, public pins и pin order, которые ожидают testbench-и.
* Если specification, verification plan и optional netlist расходятся, используй contract из `verification_plan.md`.
* Не используй internal nodes реального DUT как public interface mock-а.
* Не подключай PDK/foundry models.
* Mock должен быть deterministic, быстрым и simulator-friendly.
* Значения mock-а должны находиться внутри acceptance limits с разумным запасом, не на границе.

## Требование к HDL21

`mock_device.py` должен реально использовать HDL21 для описания схемы и экспорта SPICE.

Правила:

* public ports/top wrapper описывай как HDL21 module;
* обычные элементы mock-а описывай через HDL21 instances/primitives/helpers;
* SPICE экспортируй через HDL21 netlisting/export flow;
* не заменяй HDL21 генерацию полной ручной генерацией SPICE-текста;
* не используй HDL21 только как декларацию port list поверх полностью вручную написанного SPICE;
* если нужное behavioral поведение не выражается нормально средствами HDL21, можно использовать небольшой raw-SPICE behavioral helper;
* Если используется raw-SPICE behavioral helper, public top wrapper всё равно должен генерироваться через HDL21. Raw helper может быть только internal subckt/model/include, подключённый из HDL21-generated wrapper;
* raw-SPICE helper должен быть изолирован, документирован и использоваться только для simulator-specific behavioral core;
* top wrapper, public contract и вся выражаемая через HDL21 обвязка всё равно должны генерироваться через HDL21.


## Поведение mock DUT

Прочитай `Acceptance Test Matrix` из `verification_plan.md` и реализуй минимальное внешнее поведение, нужное для всех planned checks.

Для каждой строки test matrix проверь:

* какие public pins будут driven;
* какие public outputs или supply currents будут измеряться;
* какие режимы, sweep-и, ramp-ы, OP/DC/TRAN/AC/statistical runs нужны;
* какие метрики должны быть измеримы.

Если несколько метрик извлекаются из одного waveform/analysis, mock должен поддерживать их согласованно. Например, rising/falling threshold и hysteresis должны получаться из одной hysteretic response, а transient drop/overshoot/average drop — из одного transient response.

## Параметры mock-а

Вынеси основные constants в начало `mock_device.py`:

* nominal output/reference/current values;
* thresholds and hysteresis values;
* current consumption values;
* delay/time-constant/settling parameters;
* AC/PSRR/stability surrogate parameters, если такие проверки есть;
* statistical surrogate parameters, если verification plan требует statistical checks.

## Coverage awareness

Mock должен корректно работать во всех conditions/runs, перечисленных в `verification_plan.md`.

* Если sweep-ится supply/reference/control pin, mock должен реагировать на этот public pin или сохранять валидное измеримое поведение во всём sweep диапазоне.
* Если есть mode control, bypass, enable, reset или test mode, mock должен явно реализовать эту public-pin логику.
* Если есть supply-current checks, mock должен создавать измеримый ток через соответствующие supply pins с правильной величиной и стабильным sign convention.
* Если есть AC tests, mock должен иметь AC-observable path, достаточный для извлечения метрики.
* Если есть statistical/Monte Carlo checks, mock должен позволять pipeline запускаться, но не должен притворяться реальной statistical validation.

## Ngspice smoke check

Создай временный smoke deck:

```text
mock_device_smoke.sp
```

Smoke deck нужен только для проверки, что `mock_device.sp` парсится, инстанцируется и запускается в ngspice.

Smoke deck должен:

* include `mock_device.sp`;
* instantiate mock DUT with exact public DUT contract and pin order;
* drive all supply, ground, analog input, digital/control, reference, bias, enable/reset pins to safe nominal values from `verification_plan.md`;
* connect required public feedback pins according to nominal operating setup, если такие pins есть;
* add simple loads or high-value resistors where needed to avoid floating nodes;
* run at least `.op` and a short `.tran`.

Запусти:

```bash
ngspice -b -o mock_device_smoke.log mock_device_smoke.sp
```

Если есть ошибки, исправляй `mock_device.py`, заново генерируй `mock_device.sp`, снова запускай smoke check и повторяй до успешного запуска.

После успешного smoke check удали временные файлы:

```text
mock_device_smoke.sp
mock_device_smoke.log
```

Если smoke check не проходит из-за blocker-а, оставь log для диагностики и явно сообщи blocker.

## Финальный чеклист

Перед завершением проверь:

* `mock_device.py` реально использует HDL21 generation, а не ручную генерацию всего SPICE netlist;
* generated SPICE содержит ожидаемый `.subckt`/top wrapper и pin order;
* `mock_device.sp` сгенерирован из `mock_device.py`;
* planned checks из Acceptance Test Matrix имеют поддержанное mock behavior;
* measured outputs/currents будут измеримыми там, где это нужно;
* mock не требует PDK/foundry includes;
* нет обращения к internal DUT nodes;
* smoke check в ngspice прошёл;
* временные smoke files удалены после успешной проверки.

## Финальный ответ пользователю

Ответь кратко:

* какие файлы созданы/обновлены;
* какой DUT contract реализован;
* какие planned checks поддержаны mock behavior;
* удалось ли сгенерировать SPICE через HDL21 flow;
* прошёл ли ngspice smoke check;
* какие limitations/blockers остались, если есть.

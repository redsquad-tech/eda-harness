---
name: spec-to-verification-plan
description: Используй этот skill чтобы создать verification_plan.md из спеки
---

# Skill: Spec to Verification Plan

## Входные данные

* Specification: PDF, Markdown, текст или другой документ.
* Optional DUT netlist: SPICE или HDL21.

## Выход

Создай или обнови файл:

```text
verification_plan.md
```

`verification_plan.md` всегда пиши на английском.

## Структура `verification_plan.md`

Используй такую структуру:

```markdown
# <BLOCK_NAME> Verification Plan

## 1. Purpose and Scope
## 2. DUT Interface and Signal Interpretation
## 3. Specification Interpretation Notes
## 4. Operating Conditions and Coverage Presets
## 5. Acceptance Test Matrix
### 5.1 Presets
### 5.2 Test Matrix
```

## Общие правила

* План должен быть black-box at the DUT boundary.
* Testbenches must drive only documented public pins.
* Testbenches may observe only documented public outputs, public interface pins, and supply-source currents.
* Не используй internal DUT nodes, internal instances или implementation-specific subcircuits как acceptance observability points.
* Покрой все requirements из спецификации.
* Не выдумывай requirements, numeric limits, corner names, statistical assumptions или DUT behavior.
* Requirements и operating conditions имеют приоритет над historical/simulated/reference results.
* Historical/simulated/reference results можно использовать для понимания intent, но не как acceptance limits, если спека явно не задаёт их как требования.
* Если requirement неоднозначен, выбери наиболее согласованную инженерную интерпретацию и зафиксируй её в notes.
* Если неоднозначность блокирует составление плана, задай пользователю вопрос.
* План должен быть кратким, детерминированным и достаточным для последующей реализации приемочных testbench-ей.

## DUT Interface and Signal Interpretation

Извлеки public DUT interface из спецификации и сверяй его с optional netlist.

Используй таблицу:

```markdown
| Pin | Role | Verification Usage |
|---|---|---|
| `<pin>` | `<role>` | `<how testbenches drive or observe this pin>` |
```

После таблицы укажи intended DUT contract.

Для SPICE:

```spice
XDUT <pin1> <pin2> ... <pinN> <subckt_name>
```

Для HDL21:

```python
dut = <module_name>(
    <pin1>=...,
    <pin2>=...,
)
```

Если нетлист не передан, сформируй expected public contract по pin list из спецификации и укажи, что actual wrapper/pin order must be confirmed when the implementation netlist is connected.

## Specification Interpretation Notes

Используй таблицу:

```markdown
| Item | Interpretation |
|---|---|
| `<ambiguity / inconsistency / assumption>` | `<chosen interpretation for acceptance verification>` |
```

Фиксируй только то, что влияет на verification, например:

* противоречия в signal polarity;
* typo в pin names, metric names или conditions;
* inconsistent supply/signal naming;
* mismatch между specification pin list и netlist ports;
* unclear nominal condition;
* unclear current sign convention;
* unclear requirement scope;
* unclear distinction между requirement и reference/simulated data;
* assumptions для coverage, PVT или Monte Carlo.

## Operating Conditions and Coverage Presets

Извлеки operating conditions из спецификации.

Используй таблицу:

```markdown
| Condition | Nominal Value | Acceptance Coverage Values |
|---|---:|---|
| `<condition>` | `<nominal>` | `<values to cover>` |
```

Определи reusable presets для nominal conditions, sweeps, PVT sets, transient stimuli и statistical conditions, когда они нужны для проверки требований.

Coverage strategy должна следовать спецификации и инженерному смыслу:

* Включай coverage по тем условиям, которые могут влиять на проверяемое требование.
* Coverage должен быть конкретным: в матрице не используй `optional`, `if required`, `if requested`, `TBD` как runnable coverage.
* Если значение зависит от конкретного теста, пиши `test-dependent`, а не `TBD`.
* Если для обязательного coverage не хватает данных, вынеси это в assumptions/blockers; не создавай фиктивные presets/runs.
* PVT включай, когда требование должно выполняться across process/voltage/temperature, когда это следует из operating conditions, requirement wording, simulated-condition references или природы проверяемой метрики.
* Monte Carlo/statistical verification включай, когда спецификация задаёт variation, sigma, mismatch, yield или другой statistical requirement.
* Не добавляй process/Monte Carlo runs как заготовку на будущее, если спецификация не требует такой проверки.
* Для one-dimensional sweeps явно напиши, что меняется только одна группа условий, остальные остаются nominal.
* Full-combination coverage используй только когда это явно требуется или инженерно необходимо; иначе предпочитай компактные one-dimensional sweeps или осмысленные grouped presets.

## Acceptance Test Matrix

Используй таблицу:

```markdown
| Testbench | Specification Coverage | Test Condition / Stimulus | Condition Coverage | Measurement Method | Acceptance Criteria |
|---|---|---|---|---|---|
| `<testbench_name>` | `<requirements covered>` | `<stimulus and setup>` | `<presets/runs>` | `<metric extraction>` | `<pass/fail criteria>` |
```

Для каждой строки:

* `Testbench`: выбери короткое `snake_case` имя, derived from the requirement and analysis type.
* `Specification Coverage`: перечисли exact requirement names или normalized metric names из спецификации.
* `Test Condition / Stimulus`: опиши driven pins, supplies, references, loads, mode controls, OP/DC/TRAN/AC/statistical stimulus и public-pin connections.
* `Condition Coverage`: укажи конкретные presets/runs, которые должны быть выполнены.
* `Measurement Method`: объясни, как метрика извлекается из simulation results.
* `Acceptance Criteria`: укажи numeric pass/fail limits with units. Qualitative criterion допускается только если численного требования нет.

Правила группировки testbench-ей:

* Один testbench должен покрывать все связанные метрики, которые извлекаются из одного и того же setup/stimulus/waveform/analysis.
* Не создавай отдельный testbench только для derived metric, если она вычисляется из метрик того же прогона.
* Hysteresis, threshold pairs, droop/overshoot/average drop, gain/phase/gain-margin и похожие связанные метрики должны группироваться в один reusable testbench, если для них нужен один общий stimulus или analysis.
* Разделяй testbench-и только когда реально отличается setup, stimulus, analysis type или observability.

Measurement rules:

* Для DC/OP metrics измеряй значение after operating point converges.
* Для ramp thresholds измеряй swept input value at the relevant output transition.
* Для hysteresis задай формулу из rising/falling thresholds.
* Для supply currents report positive current consumption into the DUT и зафиксируй simulator sign normalization.
* Для transient droop/overshoot/settling metrics определи baseline и measurement window.
* Для AC metrics определи injection point, observed node, frequency range если он задан, и extracted metric.
* Для statistical metrics определи per-sample measurement и final statistic.
* Не используй `smoke-only` для метрики, которую можно измерить по спецификации.

## Финальный чеклист

Перед завершением проверь:

* все public pins отражены в DUT interface table;
* DUT contract указан;
* verification-relevant ambiguities documented;
* operating conditions и coverage presets defined;
* каждый specification requirement есть в test matrix;
* каждая строка testbench имеет stimulus, coverage, measurement method и acceptance criteria;
* связанные метрики сгруппированы в минимальное число reusable testbench-ей;
* coverage в test matrix конкретный, без optional/future/TBD runnable runs;
* PVT/statistical coverage included where required by the specification or engineering necessity;
* no internal DUT nodes are used as acceptance observability points;
* no invented requirements or numeric limits;
* plan is concise and ready for testbench implementation.

## Финальный ответ пользователю

После создания или обновления `verification_plan.md` ответь кратко:

* created/updated file name;
* selected DUT contract;
* main requirement groups covered;
* PVT/Monte Carlo decisions and why;
* blockers or assumptions, if any.

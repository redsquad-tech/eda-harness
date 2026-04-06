# Opamp AZ Tracking

## Scope

Трекер текущего состояния разработки ОУ с auto-zero в `sky130`.

Цель:
- держать в одном месте актуальные метрики
- не повторять уже проверенные тупиковые эксперименты
- фиксировать реальные блокеры перед tape-out

## Current Status

### High-Level Summary

- `opamp_core` на новой архитектуре собран и выглядит рабочим на nominal.
- `opamp_az_top` на `TT nominal` проходит top-level budget по исправленной методике измерения.
- Главный blocker сейчас не nominal, а сильная чувствительность `AZ` к corner conditions.
- До tape-out ещё далеко: нет `MC`, нет `PEX`, нет layout/post-layout signoff.

### Current Architecture

`opamp_core`:
- `gain_stage -> second_stage -> output_stage`

`opamp_az_top`:
- `frontend_az -> opamp_core`

## Current Metrics

### Opamp Core Nominal

Источник:
- `components/opamp_core.py`
- `tests/structural/opamp_core/*`

| Metric | Target | Current | Status |
|---|---:|---:|---|
| Open-loop gain | `>= 75 dB` | `89.74 dB` | OK |
| GBW @ 1 pF | `500 kHz ... 1 MHz` | `941.7 kHz` | OK |
| Phase margin @ 1 pF | `>= 30 deg` | `107.7 deg` | OK |
| Gain margin | `>= 5 dB` | `inf` | OK |
| Quiescent current | `<= 15 uA` | `9.77 uA` | OK |
| Output swing low | `<= 0.1 V` | `0.100257 V` | borderline |
| Output swing high | `>= 1.7 V` | budget test passes | OK |
| Output current | `>= ±25 uA` | budget/ char tests pass | OK |
| Disabled leakage | `<= 15 nA` | budget test passes | OK |

### AZ Top-Level Nominal

Источник:
- `components/opamp_az_top.py`
- `tests/structural/opamp_az_top/test_opamp_az_top__budget__precision_ppa.py`

Важно:
- product-level `pedestal` и `settling` сейчас считаются по usable interior window `PHI2`, а не по всей фазе вместе с edge feedthrough

| Metric | Target | Current | Status |
|---|---:|---:|---|
| Residual offset after AZ | `<= 150 uV` | `2.09 uV` | OK |
| Pedestal, whole PHI2 | debug only | `69.59 uV` | info |
| Pedestal, `mid50` window | `<= 50 uV` | `31.67 uV` | OK |
| Settling residue, whole PHI2 | debug only | `69.59 uV` | info |
| Settling residue, `mid50` window | `<= 30 uV` | `12.31 uV` | OK |

### AZ Top-Level Reduced PVT

Источник:
- `components/opamp_az_top.py: run_reduced_pvt_test`
- `tests/structural/opamp_az_top/test_opamp_az_top__char__reduced_pvt.py`

| Case | Residual Offset, uV | Pedestal Mid50, uV | Settling Mid50, uV | Status |
|---|---:|---:|---:|---|
| `TT 1.80V 27C` | `2.09` | `31.67` | `12.31` | good |
| `SS 1.60V 125C` | `913.74` | `397.12` | `121.71` | fail |
| `FF 1.98V -40C` | `2198.80` | `1081.54` | `263.26` | fail |
| `SS 1.60V -40C` | `82.26` | `3.75` | `1.11` | good |
| `FF 1.98V 125C` | `3284.53` | `369.05` | `15.35` | fail |

Worst reduced-PVT:
- `worst_residual_offset_uV = 3284.53`
- `worst_pedestal_mid50_uV = 1081.54`
- `worst_settling_mid50_uV = 263.26`

## What We Learned

### 1. Core Was Not the Main Blocker

После пересборки `opamp_core` и правки benches выяснилось:
- core на nominal выглядит достаточно сильным
- drive удалось поднять после перехода на `output_stage`
- текущий главный blocker сидит не в `core`, а в `AZ`-части на corners

### 2. Some Earlier Red Results Were Measurement Artifacts

Было подтверждено:
- часть старых `open_loop / PM / GM` метрик была искажена bench-методикой
- часть старых `AZ pedestal / settling` метрик считала edge feedthrough как полезную amplify-phase ошибку

Из-за этого были внесены правки:
- `opamp_core` gain и loop metrics разведены
- `opamp_az_top` budget переведён на interior-window measurement
- standalone `frontend_az` test переведён в characterization, а не product-budget

### 3. Current Two-Phase AZ Is Too Corner-Sensitive

На `TT nominal` всё хорошо.
На reduced PVT `AZ` разваливается.

Вывод:
- текущая sampled correction topology работает как demonstration of concept
- но не даёт достаточной robustness для signoff

## Experiments Already Tried

### Experiments That Helped

1. Новый `opamp_core` path:
- `gain_stage -> second_stage -> output_stage`

2. Bias-aware `output_stage`
- помог восстановить полезный gain и drive на core

3. Ослабленный correction path в `frontend_az`
- лучший nominal кандидат:
  - `c_az = 50 fF`
  - `r_vcm_top = 1e3`
  - `r_vcm_bot = 5`

4. Перевод top-level AZ budget на interior window
- показал, что реальное useful-window поведение лучше, чем whole-phase p2p

### Experiments That Did Not Help

1. Простая RC-развязка между SC-node и `VXP/VXN`
- ухудшала offset
- не закрывала pedestal/residue

2. Mirrored correction на `VXN`
- быстро ухудшала `pedestal` и `settling`

3. Reset входов core в внутренний `VCM`
- ломал offset на порядки

4. Short `VXP/VXN` during `PHI1`
- ухудшал `pedestal`

5. Delayed short correction pulse inside `PHI2`
- сильно ухудшал residual offset

6. Простое уменьшение dead-time
- ломало offset

7. Простое увеличение `c_az`
- не давало достаточного выигрыша

## Current Best Known Nominal AZ Point

В `opamp_az_top` по умолчанию сейчас стоит:
- `FrontendAzParams(c_az=5e-14, r_vcm_top=1e3, r_vcm_bot=5)`

Это лучший найденный nominal balance для текущей topology.

## What Is Missing Before Tape-Out

### Must-Have

1. Починить corner sensitivity у `AZ`
- это главный blocker

2. Full top-level PVT
- после стабилизации topology

3. Monte Carlo
- residual offset
- pedestal
- settling
- startup robustness

4. Layout / post-layout cycle
- layout
- DRC
- LVS
- PEX
- post-layout sims

### Nice-to-Have But Not Immediate

- более явная separation между debug metrics и signoff metrics
- cleaner reporting around `mid50` / `mid40`

## Recommended Next Steps

### Next Schematics Step

Не крутить дальше мелкие `R/C`.

Следующий реальный шаг:
- перепроектировать `frontend_az` в более robust topology

Наиболее вероятные направления:
1. ввести явную третью фазу:
   - `PHI1 = sample_zero`
   - `PHI2 = correction_apply`
   - `PHI3 = signal_settle`
2. или перейти на более классическую SC auto-zero topology вокруг входной пары core

### Next Verification Step

После новой `frontend_az` topology:
1. прогнать nominal top-level budget
2. прогнать reduced PVT
3. если reduced PVT стал приемлемым, запускать:
   - full PVT
   - MC
   - layout / PEX

## Practical Note

На сегодня корректное утверждение такое:

- `TT nominal`: устройство выглядит рабочим
- `reduced PVT`: устройство ещё не готово
- tape-out readiness: нет

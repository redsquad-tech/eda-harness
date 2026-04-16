# opamp/v4: краткая сводка для анализа

## Что уже исправлено

- `xbias` перестроен:
  - PMOS bias через diode-stack + `mn_psink`
  - NMOS bias через stacked chain
- добавлен `iref_int` clamp в `disabled`
- `vout_to_vtest` переведён на внешний `vout`
- test/debug path приведён в рабочее состояние
- Monticelli bridge уже исправлялся по полярностям

## Что по-прежнему не работает на top-level

- nominal open-loop:
  - `AOL = -167.6 dB`
  - `GBW = NaN`
  - `PM = NaN`
- `VOUT` в nominal сидит почти на `AVDD`
- output drive `+/-20 uA` провален
- `enabled IQ = 17.63 uA`
- `disabled current = 250.7 nA`

## Что уже известно по debug sweep

Команда:

```bash
python3 -m devices.hogervorst_page12_sky130_opa.debug_sweeps
```

Артефакты:

- `devices/hogervorst_page12_sky130_opa/debug_sweeps_v4.md`
- `devices/hogervorst_page12_sky130_opa/debug_sweeps_v4.json`

### 1. `VIN -> DRV` почти мёртв

- `vinp_to_drv_p_sign = flat`
- `vinp_to_drv_n_sign = flat`

### 2. `DRV -> VGP/VGN` почти мёртв

- `vinp_to_vgp_sign = flat`
- `vinp_to_vgn_sign = flat`

### 3. `VOUT` почти не реагирует на вход

- `vinp_rise_moves_vout = flat`
- `vinn_rise_moves_vout = flat`

### 4. Это не ошибка выбора unity-feedback polarity

- `feedback_to_vinn_drive_vinp: drive_to_vout_sign = flat`
- `feedback_to_vinp_drive_vinn: drive_to_vout_sign = flat`

### 5. Rail-gating не является корнем проблемы

Сравнение `classab_output_stage` vs raw push-pull без `header/footer`:

- `gated vgp_to_vout_sign = flat`
- `raw vgp_to_vout_sign = flat`
- `gated vgn_to_vout_sign = flat`
- `raw vgn_to_vout_sign = flat`

То есть чувствительность не появляется даже без rail-gating switches.

### 6. Нижнее плечо реагирует по току, но не по напряжению

- `gated vgn_to_iq_sign = positive`
- `raw vgn_to_iq_sign = positive`
- при этом `vgn_to_vout_sign = flat`

## Текущий вывод

Проблема не в debug/testbench polarity и не только в bias.

Сейчас тракт почти плоский на всех трёх участках:

- `VIN -> DRV`
- `DRV -> VGP/VGN`
- `VGP/VGN -> VOUT`

И rail-gating не объясняет это поведение.

## Что отправлено для анализа

- чистый netlist без debug MUX / replica / scan-proxy:
  - `devices/hogervorst_page12_sky130_opa/neuron_core_oa_sky130.spice`
- рабочий DUT netlist:
  - `devices/hogervorst_page12_sky130_opa/neuron_core_oa_sky130.spice`
- debug summary:
  - `devices/hogervorst_page12_sky130_opa/debug_sweeps_v4.md`
- spec compliance:
  - `devices/hogervorst_page12_sky130_opa/spec_compliance_v4.md`

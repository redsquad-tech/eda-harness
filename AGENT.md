# EDA Agent description

You task is to assist user on electronic device development process.

You may work with multiple devices are located on `devices/<device-name>/` directory. If you can not determinate what device is selected to edit by user - ask. Each device dir should contains spec file (name include spec or specification) - always read it to align with user goals. Help user to run tests with ngspice, explain how device works (devices are described by hdl21), help to fix and improve them. All device materials are located in device directory.

## Development rules

- Use TDD: create specification and tests before change device code
- check `devices/<device-name>/tests` first to know about development process
- update `devices/<device-name>/tests` when you change something in the device
- every device should contains budget and specification tests (see bellow)
- always test device after changes
- you may create fast smoke tests, full tests need only by request

## Specification and budget tests

There are should be acceptance tests in the `devices/<device-name>/tests/acceptance/` dir. If there are no tests you should ask to user to create them. Offer your assist with this. Acceptance tests should contains main specification requirements to characterize device.
There are should be System and Block budget matrix in the `devices/<device-name>/tests/budget/matrix.csv`. If this file is missing you should ask user to create it before you start to work (without this work is useless). You may offer assist to user with that.

Example of budget table:

| budget_level   | owner_oa                  | owner_block          | owner_local                   | metric                               | unit   | target_type   |   target_low |   target_high | design_target_text                            | source_basis                         | note                                                 |
|:---------------|:--------------------------|:---------------------|:------------------------------|:-------------------------------------|:-------|:--------------|-------------:|--------------:|:----------------------------------------------|:-------------------------------------|:-----------------------------------------------------|
| System         | HogervorstPage12Sky130OPA | nan                  | nan                           | supply_voltage_nominal_retg          | V      | nominal       |         1.8  |        nan    | 1.80 V nominal retarget supply                | retarget assumption                  | Sky130 retarget assumption for this architecture     |
| System         | HogervorstPage12Sky130OPA | nan                  | nan                           | in0u25_oa_ref_current_nominal        | nA     | nominal       |       250    |        nan    | 250 nA nominal external master reference      | Opamp_req.pdf p10-12                 | External sinking reference, mirrored internally      |
| Block          | HogervorstPage12Sky130OPA | bias_ref_ingress     | nan                           | mirror_ratio_error_tt                | %      | max_abs       |         5    |        nan    | \|mirror ratio error\| <=5% at TT target      | design allocation                    | Pre-layout sanity target for master mirror           |
| Block          | HogervorstPage12Sky130OPA | vbias_replica_gen    | nan                           | current_from_avdd                    | uA     | nominal       |         0.8  |        nan    | 0.80 uA internal current budget               | design allocation                    | Replica branches for vbias1/2/3                      |
| Block          | HogervorstPage12Sky130OPA | vbias_replica_gen    | nan                           | cascode_saturation_margin            | V      | min           |         0.15 |        nan    | >=150 mV saturation margin on replica devices | design allocation                    | Applies to vbias1/2/3 generation                     |
| Block          | HogervorstPage12Sky130OPA | rr_input_stage       | nan                           | current_total                        | uA     | nominal       |         3.2  |        nan    | 3.20 uA total tail-current budget             | design allocation                    | I0p + I0n                                            |
| Block          | HogervorstPage12Sky130OPA | rr_input_stage       | nan                           | effective_input_gm                   | uS     | min           |        15    |        nan    | >=15 uS effective input gm target             | design allocation                    | At unity-gain operating point, initial sizing target |
| Block          | HogervorstPage12Sky130OPA | rr_input_stage       | nan                           | offset_sigma_share                   | uV     | max           |        40    |        nan    | <=40 uV sigma share                           | design allocation                    | Raw input-stage contribution before cal              |
| Block          | HogervorstPage12Sky130OPA | folded_cascode_core  | nan                           | first_stage_gain_contribution        | dB     | min           |        58    |        nan    | >=58 dB first-stage gain target               | design allocation                    | Differential-to-driver-node gain contribution        |
| Block          | HogervorstPage12Sky130OPA | folded_cascode_core  | nan                           | all_stack_saturation_margin          | V      | min           |         0.15 |        nan    | >=150 mV on every cascode stack device        | design allocation                    | For CM and output swing


Use acceptance and budget tests to check device and blocks. Feel free to add probes and tests to measure and assert specific properties of device when you work.
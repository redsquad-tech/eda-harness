#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ALL_TESTS="dc_iq dynamic_load_tran psrr_ac loop_stability_ac vout_variation_mc"
DEFAULT_TESTS="dc_iq dynamic_load_tran psrr_ac loop_stability_ac"

usage() {
  cat <<'USAGE'
Usage:
  ./run_all.sh [--sim auto|ngspice|spectre] [--tests "..."] [--corners "..."] [--outdir PATH] [--csv PATH]
  ./run_all.sh --list-tests

Examples:
  ./run_all.sh --sim spectre
  ./run_all.sh --sim ngspice --corners typical
  ./run_all.sh --sim spectre --tests "dc_iq psrr_ac"

Configure DUT, models and corners through env.example / env.local.
USAGE
}

command_exists() { command -v "$1" >/dev/null 2>&1; }
abs_path() {
  case "${1:-}" in
    "") return 0 ;;
    /*) printf '%s\n' "$1" ;;
    *) printf '%s\n' "$(pwd)/$1" ;;
  esac
}
require_file() {
  if [ ! -f "$1" ]; then
    echo "ERROR: file not found: $1" >&2
    exit 2
  fi
}
safe_name() { printf '%s' "$1" | sed 's/[^A-Za-z0-9_-]/_/g'; }
sed_escape() { printf '%s' "$1" | sed -e 's/[\&|]/\\&/g'; }

SIM="${LDO_DAO_SIMULATOR:-auto}"
TESTS="${LDO_DAO_TESTS:-$DEFAULT_TESTS}"
CORNERS="${LDO_DAO_CORNERS:-typical}"
OUTDIR="${LDO_DAO_OUTDIR:-}"
CSV_OUT="${LDO_DAO_RESULTS_CSV:-$ROOT_DIR/sky130_converted_results.csv}"

while [ $# -gt 0 ]; do
  case "$1" in
    --sim) shift; SIM="${1:-}" ;;
    --tests) shift; TESTS="${1:-}" ;;
    --corners) shift; CORNERS="${1:-}" ;;
    --outdir) shift; OUTDIR="${1:-}" ;;
    --csv) shift; CSV_OUT="${1:-}" ;;
    --list-tests) echo "$ALL_TESTS"; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift || true
done

if [ "$TESTS" = "all" ]; then TESTS="$ALL_TESTS"; fi

NGSPICE="${LDO_DAO_NGSPICE:-ngspice}"
SPECTRE_MDL="${LDO_DAO_SPECTRE_MDL:-spectremdl}"
NGSPICE_ARGS="${LDO_DAO_NGSPICE_ARGS:-}"
SPECTRE_MDL_ARGS="${LDO_DAO_SPECTRE_MDL_ARGS:-}"

if [ "$SIM" = "auto" ]; then
  if command_exists "$SPECTRE_MDL"; then
    SIM="spectre"
  elif command_exists "$NGSPICE"; then
    SIM="ngspice"
  else
    echo "ERROR: cannot find spectremdl or ngspice. Set --sim and simulator path env." >&2
    exit 127
  fi
fi
case "$SIM" in ngspice|spectre) ;; *) echo "ERROR: simulator must be auto, ngspice, or spectre" >&2; exit 2 ;; esac

DUT_NETLIST="${LDO_DAO_DUT_NETLIST:-$ROOT_DIR/examples/device_mock.sp}"
DUT_NETLIST_ABS="$(abs_path "$DUT_NETLIST")"
DUT_SUBCKT="${LDO_DAO_DUT_SUBCKT:-ldo_dao}"
DUT_STYLE="${LDO_DAO_DUT_STYLE:-spice}"
MODEL_LIB="${LDO_DAO_MODEL_LIB:-}"
MODEL_INCLUDE="${LDO_DAO_MODEL_INCLUDE:-}"
MODEL_STYLE="${LDO_DAO_MODEL_STYLE:-}"
MODEL_INCLUDE_STYLE="${LDO_DAO_MODEL_INCLUDE_STYLE:-}"
IQ_SIGN="${LDO_DAO_IQ_SIGN:--1}"
MC_SAMPLES="${LDO_DAO_MC_SAMPLES:-50}"
MC_SEED="${LDO_DAO_MC_SEED:-1}"
MC_MODEL_CORNER="${LDO_DAO_MC_MODEL_CORNER:-}"

if [ -z "$MODEL_STYLE" ]; then
  if [ "$SIM" = "spectre" ]; then MODEL_STYLE="spectre"; else MODEL_STYLE="spice"; fi
fi
if [ -z "$MODEL_INCLUDE_STYLE" ]; then MODEL_INCLUDE_STYLE="$MODEL_STYLE"; fi

require_file "$DUT_NETLIST_ABS"
if [ -n "$MODEL_LIB" ]; then require_file "$(abs_path "$MODEL_LIB")"; fi
for inc in $MODEL_INCLUDE; do require_file "$(abs_path "$inc")"; done

case "$DUT_STYLE" in spice|spectre) ;; *) echo "ERROR: LDO_DAO_DUT_STYLE must be spice or spectre" >&2; exit 2 ;; esac
case "$MODEL_STYLE" in spice|spectre) ;; *) echo "ERROR: LDO_DAO_MODEL_STYLE must be spice or spectre" >&2; exit 2 ;; esac
case "$MODEL_INCLUDE_STYLE" in spice|spectre) ;; *) echo "ERROR: LDO_DAO_MODEL_INCLUDE_STYLE must be spice or spectre" >&2; exit 2 ;; esac
if [ "$SIM" = "ngspice" ] && { [ "$MODEL_STYLE" = "spectre" ] || [ "$MODEL_INCLUDE_STYLE" = "spectre" ] || [ "$DUT_STYLE" = "spectre" ]; }; then
  echo "ERROR: ngspice run needs SPICE-format DUT/models. Use LDO_DAO_*_STYLE=spice." >&2
  exit 2
fi

if [ -z "$OUTDIR" ]; then OUTDIR="$ROOT_DIR/results/$(date +%Y%m%d_%H%M%S)_$SIM"; fi
OUTDIR="$(abs_path "$OUTDIR")"
mkdir -p "$OUTDIR" "$ROOT_DIR/results"
ln -sfn "$OUTDIR" "$ROOT_DIR/results/latest"
SUMMARY="$OUTDIR/summary.txt"
: > "$SUMMARY"

map_corner() {
  local logical="$1" pair key val
  for pair in ${LDO_DAO_CORNER_MAP:-}; do
    key="${pair%%:*}"
    val="${pair#*:}"
    if [ "$key" = "$logical" ]; then printf '%s\n' "$val"; return 0; fi
  done
  printf '%s\n' "$logical"
}

map_mc_corner() {
  local base="$1"
  if [ -n "$MC_MODEL_CORNER" ]; then printf '%s\n' "$MC_MODEL_CORNER"; return 0; fi
  case "$base" in
    tt|ff|ss|fs|sf|ll|hh|hl|lh) printf '%s_mm\n' "$base" ;;
    *_mm|mc) printf '%s\n' "$base" ;;
    *) printf '%s\n' "$base" ;;
  esac
}

test_file() {
  case "$1" in
    dc_iq) echo "$ROOT_DIR/tests/dc_iq.sp" ;;
    dynamic_load_tran) echo "$ROOT_DIR/tests/dynamic_load_tran.sp" ;;
    psrr_ac) echo "$ROOT_DIR/tests/psrr_ac.sp" ;;
    loop_stability_ac) echo "$ROOT_DIR/tests/loop_stability_ac.sp" ;;
    vout_variation_mc) echo "$ROOT_DIR/tests/vout_variation_mc.sp" ;;
    *) return 1 ;;
  esac
}

ng_control_file() { echo "$ROOT_DIR/measures/ngspice/$1.control"; }
sp_mdl_file() { echo "$ROOT_DIR/measures/spectre/$1.mdl"; }

write_common_header() {
  {
    echo "LDO_DAO acceptance suite"
    echo "  simulator    : $SIM"
    echo "  outdir       : $OUTDIR"
    echo "  DUT netlist  : $DUT_NETLIST_ABS"
    echo "  DUT subckt   : $DUT_SUBCKT"
    echo "  DUT style    : $DUT_STYLE"
    echo "  model lib    : ${MODEL_LIB:-<none>}"
    echo "  model style  : $MODEL_STYLE"
    echo "  corners      : $CORNERS"
    echo "  tests        : $TESTS"
    echo
  } | tee -a "$SUMMARY"
}

write_results_csv() {
  local out="$1"
  awk -v project="ldo_dao_acceptance_suite" -v source="$SUMMARY" '
    BEGIN {
      FS = " "
      OFS = ","
      print "project,requirement,test_name,parameters,pass,metric,value,fail_reason,limit,source_log"
    }
    function q(s) {
      gsub(/"/, "\"\"", s)
      return "\"" s "\""
    }
    function req(t) {
      if (t == "dc_iq") return "1.08 V <= Vout <= 1.32 V; Iq <= 3 uA"
      if (t == "dynamic_load_tran") return "dynamic-load regulation: valid pre/post Vout; drop <= 50 mV; overshoot <= 20 mV; average drop <= 25 mV"
      if (t == "psrr_ac") return "PSRR_min >= 40 dB"
      if (t == "loop_stability_ac") return "GBW >= 100 kHz; PM >= 40 deg; GM >= 20 dB"
      if (t == "vout_variation_mc") return "Monte Carlo Vout statistics must be measurable and sigma <= 30 mV"
      return ""
    }
    function is_param(k) {
      return k == "corner" || k == "model_corner" || k == "simulator" || k == "sweep" || k == "temp_c" || k == "vdd" || k == "vref" || k == "ibias_A" || k == "iload_A" || k == "sample" || k == "samples"
    }
    function add_param(s, k) {
      if (!(k in f)) return s
      if (s == "") return k "=" f[k]
      return s "; " k "=" f[k]
    }
    function params_string(    s) {
      s = ""
      s = add_param(s, "corner")
      s = add_param(s, "model_corner")
      s = add_param(s, "simulator")
      s = add_param(s, "sweep")
      s = add_param(s, "temp_c")
      s = add_param(s, "vdd")
      s = add_param(s, "vref")
      s = add_param(s, "ibias_A")
      s = add_param(s, "iload_A")
      s = add_param(s, "sample")
      s = add_param(s, "samples")
      return s
    }
    function parse_fields(start,    i, kv, k, v) {
      delete f
      for (i = start; i <= NF; i++) {
        if (index($i, "=") == 0) continue
        split($i, kv, "=")
        if (length(kv[1]) > 0) {
          k = kv[1]
          v = substr($i, length(k) + 2)
          f[k] = v
        }
      }
    }
    function parse_run_context(    i, kv) {
      delete runctx
      for (i = 2; i <= NF; i++) {
        if (index($i, "=") == 0) continue
        split($i, kv, "=")
        runctx[kv[1]] = substr($i, length(kv[1]) + 2)
      }
    }
    function fail_metric(reason,    k) {
      if (reason == "TRAN_NOT_COMPLETED") return "simulation_status"
      if (reason == "MC_VARIATION_NOT_DETECTED") return "sigma_mV"
      if (reason ~ /^IQ_/) return "Iq_uA"
      if (reason ~ /^VOUT_/ || reason ~ /^PRE_VOUT/ || reason ~ /^AVG_VOUT/) return "Vout_V"
      for (k in f) {
        if (k != "test" && k != "reason" && !is_param(k) && k !~ /^limit_/ && k !~ /^value_/) return k
      }
      if ("value_V" in f) return "Vout_V"
      if ("value_uA" in f) return "Iq_uA"
      return ""
    }
    FNR == NR {
      if ($1 == "[RUN]") {
        parse_run_context()
        cur_corner = runctx["corner"]
        cur_model_corner = runctx["model_corner"]
        next
      }
      if ($1 == "FAIL") {
        parse_fields(2)
        if (!("corner" in f) && cur_corner != "") f["corner"] = cur_corner
        if (!("model_corner" in f) && cur_model_corner != "") f["model_corner"] = cur_model_corner
        t = f["test"]
        m = fail_metric(f["reason"])
        params = params_string()
        key = t SUBSEP m SUBSEP params
        if (f["reason"] == "TRAN_NOT_COMPLETED") invalid_tran[t] = 1
        if (reasons[key] == "") reasons[key] = f["reason"]; else reasons[key] = reasons[key] ";" f["reason"]
        for (k in f) if (k ~ /^limit_/ || k ~ /_threshold_s$/) {
          if (limits[key] == "") limits[key] = k "=" f[k]; else limits[key] = limits[key] "; " k "=" f[k]
        }
        if (f["reason"] == "TRAN_NOT_COMPLETED") {
          key = t SUBSEP "tran_stop_s" SUBSEP params
          if (reasons[key] == "") reasons[key] = f["reason"]; else reasons[key] = reasons[key] ";" f["reason"]
          for (k in f) if (k ~ /^limit_/ || k ~ /_threshold_s$/) {
            if (limits[key] == "") limits[key] = k "=" f[k]; else limits[key] = limits[key] "; " k "=" f[k]
          }
        }
      }
      next
    }
    $1 == "[RUN]" {
      parse_run_context()
      cur_corner = runctx["corner"]
      cur_model_corner = runctx["model_corner"]
      next
    }
    $1 == "RESULT" {
      parse_fields(2)
      if (!("corner" in f) && cur_corner != "") f["corner"] = cur_corner
      if (!("model_corner" in f) && cur_model_corner != "") f["model_corner"] = cur_model_corner
      t = f["test"]
      params = params_string()
      for (k in f) {
        if (k == "test" || k == "pass" || is_param(k)) continue
        if (invalid_tran[t] && t == "dynamic_load_tran" && k != "simulation_status" && k != "tran_stop_s") continue
        key = t SUBSEP k SUBSEP params
        p = (reasons[key] != "") ? "FAIL" : "PASS"
        print q(project), q(req(t)), q(t), q(params), q(p), q(k), q(f[k]), q(reasons[key]), q(limits[key]), q(source)
      }
    }
  ' "$SUMMARY" "$SUMMARY" > "$out"
}

write_ngspice_setup() {
  local model_corner="$1" out="$2"
  {
    echo "* generated setup"
    echo ".options savecurrents reltol=1e-4 abstol=1e-15 vntol=1e-9"
    echo ".param TB_VDD=3.3"
    echo ".param TB_VREF=0.80"
    echo ".param TB_IBIAS=400n"
    echo ".param TB_ILOAD_DC=15u"
    echo ".param TB_ILOAD_PULSE=30m"
    echo ".param TB_TSTART=200n"
    echo ".param TB_TPW=200p"
    echo ".param TB_TPER=100n"
    echo ".param TB_COUT_VAL=449p"
    echo
    for inc in $MODEL_INCLUDE; do echo ".include \"$(abs_path "$inc")\""; done
    if [ -n "$MODEL_LIB" ]; then echo ".lib \"$(abs_path "$MODEL_LIB")\" $model_corner"; fi
    echo ".include \"$DUT_NETLIST_ABS\""
    echo
    echo ".subckt ldo_dao_test_dut vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss"
    echo "XREAL vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss $DUT_SUBCKT"
    echo ".ends ldo_dao_test_dut"
  } > "$out"
}

run_ngspice_one() {
  local logical_corner="$1" model_corner="$2" test="$3"
  local tf cf run_dir setup top log rc
  tf="$(test_file "$test")" || { echo "ERROR: unknown test $test" | tee -a "$SUMMARY"; suite_fail=1; return; }
  cf="$(ng_control_file "$test")"
  require_file "$tf"; require_file "$cf"
  run_dir="$OUTDIR/$logical_corner/$test"
  mkdir -p "$run_dir"
  setup="$run_dir/setup.spinc"
  top="$run_dir/top.sp"
  log="$run_dir/run.log"
  if [ "$test" = "vout_variation_mc" ]; then
    model_corner="$(map_mc_corner "$model_corner")"
  fi
  write_ngspice_setup "$model_corner" "$setup"
  if [ "$test" = "dynamic_load_tran" ]; then
    {
      echo "* transient-convergence options for SKY130/ngspice dynamic-load acceptance"
      echo ".options method=gear maxord=2 reltol=0.005 vntol=10u abstol=10p chgtol=1e-12"
    } >> "$setup"
  fi
  {
    echo "* generated top deck: $test, corner=$logical_corner"
    echo ".title LDO_DAO $test $logical_corner"
    echo ".include \"$setup\""
    echo ".include \"$tf\""
    cat "$cf"
    echo ".end"
  } > "$top"

  echo "[RUN] $SIM corner=$logical_corner model_corner=$model_corner test=$test" | tee -a "$SUMMARY"
  (
    cd "$run_dir" || exit 3
    # shellcheck disable=SC2086
    "$NGSPICE" -b -o "$log" "$top" $NGSPICE_ARGS
  )
  rc=$?
  suite_runs=$((suite_runs + 1))
  if [ $rc -ne 0 ]; then
    echo "[FAIL] corner=$logical_corner test=$test rc=$rc" | tee -a "$SUMMARY"
    suite_fail=1
  elif grep -q '^FAIL ' "$log" 2>/dev/null; then
    echo "[FAIL] corner=$logical_corner test=$test" | tee -a "$SUMMARY"
    suite_fail=1
  else
    echo "[PASS] corner=$logical_corner test=$test" | tee -a "$SUMMARY"
  fi
  grep -E '^(BEGIN|RESULT|FAIL|SUMMARY)' "$log" >> "$SUMMARY" 2>/dev/null || true
  echo >> "$SUMMARY"
}

spectre_analysis() {
  case "$1" in
    dc_iq|vout_variation_mc) echo "dcOp op" ;;
    dynamic_load_tran) echo "tran1 tran stop=900n step=10p maxstep=10p errpreset=moderate" ;;
    psrr_ac|loop_stability_ac) echo "ac1 ac start=1 stop=1G dec=200" ;;
    *) return 1 ;;
  esac
}

write_spectre_top() {
  local model_corner="$1" test="$2" temp="$3" vdd="$4" vref="$5" ibias="$6" iload="$7" out="$8"
  local analysis
  analysis="$(spectre_analysis "$test")" || return 1
  {
    echo "// generated top deck: $test"
    echo "simulator lang=spectre"
    echo "global 0"
    echo "simulatorOptions options temp=$temp reltol=1e-4 vabstol=1e-9 iabstol=1e-15 savecurrents=yes"
    echo
    if [ "$MODEL_STYLE" = "spectre" ]; then
      for inc in $MODEL_INCLUDE; do echo "include \"$(abs_path "$inc")\""; done
      if [ -n "$MODEL_LIB" ]; then echo "include \"$(abs_path "$MODEL_LIB")\" section=$model_corner"; fi
    fi
    if [ "$DUT_STYLE" = "spectre" ]; then
      echo "include \"$DUT_NETLIST_ABS\""
      echo "subckt ldo_dao_test_dut vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss"
      echo "  XREAL (vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss) $DUT_SUBCKT"
      echo "ends ldo_dao_test_dut"
    fi
    echo
    echo "simulator lang=spice"
    if [ "$MODEL_STYLE" = "spice" ]; then
      for inc in $MODEL_INCLUDE; do echo ".include \"$(abs_path "$inc")\""; done
      if [ -n "$MODEL_LIB" ]; then echo ".lib \"$(abs_path "$MODEL_LIB")\" $model_corner"; fi
    fi
    echo ".param TB_VDD=$vdd"
    echo ".param TB_VREF=$vref"
    echo ".param TB_IBIAS=$ibias"
    echo ".param TB_ILOAD_DC=$iload"
    echo ".param TB_ILOAD_PULSE=30m"
    echo ".param TB_TSTART=200n"
    echo ".param TB_TPW=200p"
    echo ".param TB_TPER=100n"
    echo ".param TB_COUT_VAL=449p"
    if [ "$DUT_STYLE" = "spice" ]; then
      echo ".include \"$DUT_NETLIST_ABS\""
      echo ".subckt ldo_dao_test_dut vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss"
      echo "XREAL vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss $DUT_SUBCKT"
      echo ".ends ldo_dao_test_dut"
    fi
    echo ".include \"$(test_file "$test")\""
    echo
    echo "simulator lang=spectre"
    echo "$analysis"
  } > "$out"
}

render_mdl() {
  local in="$1" out="$2" corner="$3" sweep="$4" temp="$5" vdd="$6" vref="$7" ibias="$8" iload="$9"
  sed \
    -e "s|@CORNER@|$(sed_escape "$corner")|g" \
    -e "s|@SWEEP@|$(sed_escape "$sweep")|g" \
    -e "s|@TEMP_C@|$temp|g" \
    -e "s|@VDD@|$vdd|g" \
    -e "s|@VREF@|$vref|g" \
    -e "s|@IBIAS@|$ibias|g" \
    -e "s|@ILOAD@|$iload|g" \
    -e "s|@IQ_SIGN@|$IQ_SIGN|g" \
    -e "s|@MC_SAMPLES@|$MC_SAMPLES|g" \
    -e "s|@MC_SEED@|$MC_SEED|g" \
    "$in" > "$out"
}

run_spectre_condition() {
  local logical_corner="$1" model_corner="$2" test="$3" sweep="$4" temp="$5" vdd="$6" vref="$7" ibias="$8" iload="$9"
  local cond run_dir top mdl_template mdl raw measure log result rc
  cond="$(safe_name "${sweep}_t${temp}_vdd${vdd}_vref${vref}_ib${ibias}_ld${iload}")"
  run_dir="$OUTDIR/$logical_corner/$test/$cond"
  mkdir -p "$run_dir"
  top="$run_dir/top.scs"
  mdl_template="$(sp_mdl_file "$test")"
  mdl="$run_dir/measure.mdl"
  raw="$run_dir/raw"
  measure="$run_dir/spectre.measure"
  log="$run_dir/run.log"
  result="$run_dir/spectre_results.txt"
  require_file "$mdl_template"
  write_spectre_top "$model_corner" "$test" "$temp" "$vdd" "$vref" "$ibias" "$iload" "$top"
  render_mdl "$mdl_template" "$mdl" "$logical_corner" "$sweep" "$temp" "$vdd" "$vref" "$ibias" "$iload"
  rm -f "$result" "$measure" "$log"

  echo "[RUN] $SIM corner=$logical_corner test=$test condition=$cond" | tee -a "$SUMMARY"
  (
    cd "$run_dir" || exit 3
    # shellcheck disable=SC2086
    "$SPECTRE_MDL" $SPECTRE_MDL_ARGS -batch "$mdl" -design "$top" -raw "$raw" -measure "$measure" > "$log" 2>&1
  )
  rc=$?
  suite_runs=$((suite_runs + 1))
  if [ $rc -ne 0 ]; then
    echo "[FAIL] corner=$logical_corner test=$test condition=$cond rc=$rc" | tee -a "$SUMMARY"
    suite_fail=1
  elif [ ! -f "$result" ]; then
    echo "[FAIL] corner=$logical_corner test=$test condition=$cond reason=missing_results" | tee -a "$SUMMARY"
    suite_fail=1
  elif grep -q '^FAIL ' "$result" 2>/dev/null; then
    echo "[FAIL] corner=$logical_corner test=$test condition=$cond" | tee -a "$SUMMARY"
    suite_fail=1
  else
    echo "[PASS] corner=$logical_corner test=$test condition=$cond" | tee -a "$SUMMARY"
  fi
  grep -E '^(BEGIN|RESULT|FAIL|SUMMARY)' "$result" >> "$SUMMARY" 2>/dev/null || true
  echo >> "$SUMMARY"
}

run_spectre_test() {
  local logical_corner="$1" model_corner="$2" test="$3" temp vdd vref ibias iload
  case "$test" in
    dc_iq)
      for temp in -40 27 150; do for vdd in 2.0 3.3 3.6; do for iload in 0 15e-6; do
        run_spectre_condition "$logical_corner" "$model_corner" "$test" PVT "$temp" "$vdd" 0.80 400e-9 "$iload"
      done; done; done
      for vref in 0.72 0.88; do for iload in 0 15e-6; do
        run_spectre_condition "$logical_corner" "$model_corner" "$test" VREF 27 3.3 "$vref" 400e-9 "$iload"
      done; done
      for ibias in 300e-9 500e-9; do for iload in 0 15e-6; do
        run_spectre_condition "$logical_corner" "$model_corner" "$test" IBIAS 27 3.3 0.80 "$ibias" "$iload"
      done; done
      ;;
    dynamic_load_tran|psrr_ac|loop_stability_ac)
      for temp in -40 27 150; do for vdd in 2.0 3.3 3.6; do
        run_spectre_condition "$logical_corner" "$model_corner" "$test" PVT "$temp" "$vdd" 0.80 400e-9 15e-6
      done; done
      ;;
    vout_variation_mc)
      run_spectre_condition "$logical_corner" "$model_corner" "$test" MC 27 2.8 0.80 400e-9 0
      ;;
    *) echo "ERROR: unknown test $test" | tee -a "$SUMMARY"; suite_fail=1 ;;
  esac
}

suite_fail=0
suite_runs=0
write_common_header

if [ "$SIM" = "ngspice" ]; then
  command_exists "$NGSPICE" || { echo "ERROR: ngspice not found: $NGSPICE" >&2; exit 127; }
  for logical_corner in $CORNERS; do
    model_corner="$(map_corner "$logical_corner")"
    for test in $TESTS; do run_ngspice_one "$logical_corner" "$model_corner" "$test"; done
  done
else
  command_exists "$SPECTRE_MDL" || { echo "ERROR: spectremdl not found: $SPECTRE_MDL" >&2; exit 127; }
  for logical_corner in $CORNERS; do
    model_corner="$(map_corner "$logical_corner")"
    for test in $TESTS; do run_spectre_test "$logical_corner" "$model_corner" "$test"; done
  done
fi

echo "Suite runs: $suite_runs" | tee -a "$SUMMARY"
write_results_csv "$CSV_OUT"
echo "Results CSV: $CSV_OUT" | tee -a "$SUMMARY"
if [ $suite_fail -ne 0 ]; then
  echo "Suite status: FAIL" | tee -a "$SUMMARY"
  exit 1
else
  echo "Suite status: PASS" | tee -a "$SUMMARY"
  exit 0
fi

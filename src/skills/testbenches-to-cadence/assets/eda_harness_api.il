; Stable helpers used by generated suite-level Cadence imports.

procedure(ehAssert(condition message)
  unless(condition error("EDA_HARNESS_ASSERT: %s\n" message))
)

procedure(ehRequiredEnv(name)
  let((value)
    value = getShellEnvVar(name)
    unless(value && strlen(value) > 0
      error("missing required environment variable: %s\n" name))
    value
  )
)

procedure(ehCreateManagedLibrary(lib workDir)
  let((libPath)
    libPath = strcat(workDir "/" lib)
    unless(ddGetObj(lib)
      ddCreateLib(lib libPath)
    )
    ehAssert(ddGetObj(lib) sprintf(nil "failed to create library %s" lib))
  )
)

procedure(ehAnalysisName(kind)
  cond(
    ((kind == "op" || kind == "dc") "dc")
    ((kind == "tran") "tran")
    ((kind == "ac") "ac")
    (t error("API_UNSUPPORTED analysis kind: %s\n" kind))
  )
)

procedure(ehSetAnalysis(sess testName kind options)
  let((analysis)
    analysis = ehAnalysisName(kind)
    maeSetAnalysis(testName analysis ?enable t ?options options ?session sess)
    analysis
  )
)

procedure(ehAddOutput(sess testName name expression)
  maeAddOutput(name testName ?outputType "point" ?expr expression ?session sess)
)

; Pass the exact, generated maeSetSpec argument list. Keeping the call here
; makes unsupported local API signatures fail once with API_UNSUPPORTED.
procedure(ehSetSpec(specArgs)
  unless(getd('maeSetSpec) error("API_UNSUPPORTED maeSetSpec\n"))
  apply('maeSetSpec specArgs)
)

procedure(ehConfigureCorner(db testName cornerName proc temp modelFile section)
  let((cornerHandle model)
    cornerHandle = axlGetCorner(db cornerName)
    ehAssert(cornerHandle sprintf(nil "missing corner %s" cornerName))
    axlPutVar(cornerHandle "temperature" temp)
    model = axlPutModel(cornerHandle proc)
    ehAssert(model sprintf(nil "axlPutModel failed for %s" cornerName))
    axlSetModelFile(model modelFile)
    axlSetModelSection(model section)
    axlSetModelTest(model testName)
    axlSetEnabled(model t)
  )
)

procedure(ehWriteValidation(path expectedTests actualTests analysesValid outputsValid cornersValid)
  let((out)
    out = outfile(path "w")
    ehAssert(out sprintf(nil "cannot write validation file %s" path))
    fprintf(out "{\n")
    fprintf(out "  \"status\": \"ok\",\n")
    fprintf(out "  \"expected_tests\": %d,\n" expectedTests)
    fprintf(out "  \"actual_tests\": %d,\n" actualTests)
    fprintf(out "  \"analyses_valid\": %s,\n" if(analysesValid then "true" else "false"))
    fprintf(out "  \"outputs_valid\": %s,\n" if(outputsValid then "true" else "false"))
    fprintf(out "  \"corners_valid\": %s\n" if(cornersValid then "true" else "false"))
    fprintf(out "}\n")
    close(out)
  )
)

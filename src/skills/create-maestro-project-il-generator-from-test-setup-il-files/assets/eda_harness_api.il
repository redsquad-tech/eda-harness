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

procedure(ehCreateTest(sess testName lib cell configView)
  maeCreateTest(
    testName
    ?lib lib
    ?cell cell
    ?view configView
    ?simulator "spectre"
    ?session sess
  )
)

procedure(ehSetTestVar(sess testName name value)
  maeSetVar(
    name value
    ?typeName "test"
    ?typeValue list(testName)
    ?session sess
  )
)

procedure(ehSetAnalysis(sess testName kind options)
  let((analysis)
    analysis = cond(
      ((kind == "op") "dc")
      ((kind == "dc") "dc")
      ((kind == "tran") "tran")
      ((kind == "ac") "ac")
      (t error("unsupported analysis: %s\n" kind))
    )

    maeSetAnalysis(
      testName
      analysis
      ?enable t
      ?options options
      ?session sess
    )
  )
)

procedure(ehAddWaveform(sess testName name signalName)
  maeAddOutput(
    name testName
    ?outputType "net"
    ?signalName signalName
    ?session sess
  )
)

procedure(ehAddMetric(sess testName name expression)
  maeAddOutput(
    name testName
    ?outputType "point"
    ?expr expression
    ?session sess
  )
)

procedure(ehSetMinimum(sess testName outputName value)
  maeSetSpec(
    outputName testName
    ?gt value
    ?session sess
  )
)

procedure(ehSetMaximum(sess testName outputName value)
  maeSetSpec(
    outputName testName
    ?lt value
    ?session sess
  )
)

procedure(ehSetRange(sess testName outputName minimum maximum)
  maeSetSpec(
    outputName testName
    ?gt minimum
    ?lt maximum
    ?session sess
  )
)

procedure(ehVT(path)
  sprintf(nil "VT(\"%s\")" path)
)

procedure(ehVF(path)
  sprintf(nil "VF(\"%s\")" path)
)

procedure(ehVAR(name)
  sprintf(nil "VAR(\"%s\")" name)
)

procedure(ehCreateCorner(sess cornerName)
  maeSetCorner(
    cornerName
    ?enabled t
    ?session sess
  )
)

procedure(ehSetCornerVar(sess cornerName name value)
  maeSetVar(
    name value
    ?typeName "corner"
    ?typeValue list(cornerName)
    ?session sess
  )
)

procedure(ehAddCornerModel(
    sess cornerName modelName modelFile modelSection testName
  )
  let((sdb corner model)
    sdb = axlGetMainSetupDB(sess)
    corner = axlGetCorner(sdb cornerName)
    ehAssert(corner sprintf(nil "missing corner %s" cornerName))

    model = axlPutModel(corner modelName)
    axlSetModelFile(model modelFile)
    when(modelSection
      axlSetModelSection(model modelSection)
    )
    axlSetModelTest(model testName)
    axlSetEnabled(model t)
  )
)

procedure(ehWriteValidation(path expectedCount actualCount)
  let((out)
    out = outfile(path "w")
    ehAssert(out sprintf(nil "cannot write validation file %s" path))
    fprintf(out "{\n")
    fprintf(out "  \"status\": \"ok\",\n")
    fprintf(out "  \"expected_tests\": %d,\n" expectedCount)
    fprintf(out "  \"actual_tests\": %d\n" actualCount)
    fprintf(out "}\n")
    close(out)
  )
)

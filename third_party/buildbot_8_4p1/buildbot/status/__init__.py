import build, builder, buildstep, buildset, testresult, logfile
import subordinate, main, buildrequest

# styles.Versioned requires this, as it keys the version numbers on the fully
# qualified class name; see main/buildbot/test/regressions/test_unpickling.py
buildstep.BuildStepStatus.__module__ = 'buildbot.status.builder'
build.BuildStatus.__module__ = 'buildbot.status.builder'

# add all of these classes to builder; this is a form of late binding to allow
# circular module references among the status modules
builder.BuildStepStatus = buildstep.BuildStepStatus
builder.BuildSetStatus = buildset.BuildSetStatus
builder.TestResult = testresult.TestResult
builder.LogFile = logfile.LogFile
builder.HTMLLogFile = logfile.HTMLLogFile
builder.SubordinateStatus = subordinate.SubordinateStatus
builder.Status = main.Status
builder.BuildStatus = build.BuildStatus
builder.BuildRequestStatus = buildrequest.BuildRequestStatus

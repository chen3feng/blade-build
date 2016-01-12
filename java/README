
ReportGenerator.java is used to generate java code coverage report by use of JaCoCo API.
java_report_generator.jar is the package of class files compiled from ReportGenerator.java
by the following command:

    javac -encoding utf-8 -classpath JACOCO_HOME/lib/jacocoant.jar -d classes_dir ReportGenerator.java

Alternatively, you could use the BUILD file below. Remember to add a prebuilt java_library
target for jacocoant.jar as the dependency. Provided that JACOCO_HOME is thirdparty/jacoco:

    BUILD:
        java_library(
            name = 'report_generator',
            srcs = 'ReportGenerator.java',
            deps = '//thirdparty/jacoco:jacoco',
        )

    WORKSPACE/thirdparty/jacoco/BUILD:
        java_library(
            name = 'jacoco',
            prebuilt = True,
            binary_jar = 'lib/jacocoant.jar',
        )
    
    The generated jar is report_generator.jar in the build output directory and then you could
    rename or copy it somewhere and set the corresponding configuration in BLADE_ROOT.

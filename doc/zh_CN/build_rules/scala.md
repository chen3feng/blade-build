# 构建Scala目标

## 规则
scala_library scala_binary scala_test用法类似java，区别是编译器换成了scalac。

和java一样，scala也是JVM上的语言，因此scala目标也可以依赖java目标。


## java目标依赖scala_library

java构建目标也可以依赖scala目标，不过需要注意scala目标中应该把scala-library纳入exported依赖。
否则编译时javac会发出找不到ScalaSignature.bytes()符号的警告。

```
scala_library(
    name = 'example',
    srcs = 'Example.scala',
    exported_deps = ['//path/to/:scala_library'],
    provided_deps = ['//path/to/:scala_library'],
)
```

scala_library可以通过maven_jar来定义：

```
maven_jar(
    name = 'scala_library',
    id = 'org.scala-lang:scala-library:2.12.1',
)
```

也可以通过prebuilt的java_library来定义：
```
java_library(
    name = 'scala_library',
    binary_jar = 'scala-2.12.1/scala-library.jar',
)
```


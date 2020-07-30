# 构建Python目标 #

## py_library ##

把py源代码编译为库。

```python
py_library(
    name = 'protobuf_util',
    srcs = [
        'protobuf_util.py'
    ],
    deps = [
        ':common',               # 可以依赖别的python库
    ]
)
```

当在代码中import python模块时，需要从workspace目录开始写起。可以通过base属性来改变这个行为，比如：

```python
base = '.'
```

把模块的根路径改为当前BUILD文件所在的目录。

py_library还支持

* prebuilt=True
  主要应用于 zip 格式的包。

示例：

```python
python_library(
    name = 'protobuf-python',
    prebuilt = True,
    srcs = 'protobuf-python-3.4.1.egg',
)
```

srcs是python包的文件名，只能有一个文件，支持whl和egg两种格式

## py_binary ##

把py源代码编译为可执行文件。

```python
py_binary(
    name = 'example',
    srcs = [
        'example.py'
    ],
    deps = [
        '//python:common',
    ]
)
```

当srcs多于一个时，需要用main属性指定入口文件。

python_binary也支持base属性

编译出来的可执行文件以及打包了所有的依赖，可以直接执行。可以用 `unzip -l` 查看其中包含的文件。

属性：

* exclusions: list(str)
  打包进可执行文件的文件时，要排除的路径的模式列表，注意路径是打包后的路径，可以通过 `unzip -l` 查看，示例：

  ```python
  exclusions = ['google/protobuf/*'],
  ```

## py_test ##

编译和运行python测试代码。

```python
py_test(
    name = 'common_test',
    srcs = [
        'common_test.py'
    ],
    deps = [
        ':common',
    ],
    testdata = [...],
)
```

我们一般使用unittest库进行python单元测试。

## 使用 protobuf ##

proto文件首先需要用[proto_library](idl.md#proto_library)来描述，在py_* 的deps中引入。
blade build时会自动生成相应的python protobuf编码解码库。

在python代码中的import路径规则是，从workspace根出发，/替换为.，文件名结尾的.proto替换为_pb2，比如：

```python
# proto文件路径为 //common/base/user_info.proto
import common.base.user_info_pb2
```

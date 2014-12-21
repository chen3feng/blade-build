namespace testing {

class Test {
public:
    Test();
    virtual ~Test();
    virtual void SetUp();
    virtual void TearDown();
};

Test::Test() {}
Test::~Test() {}
void Test::SetUp() {}
void Test::TearDown() {}

namespace internal {
class TestFactoryBase;
int GetTestTypeId() { return 0; }
void MakeAndRegisterTestInfo(char const*, char const*, char const*, char const*, void const*, void (*)(), void (*)(), testing::internal::TestFactoryBase*) {
}
}

}

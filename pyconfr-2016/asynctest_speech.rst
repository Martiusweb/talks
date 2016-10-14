1/
Hi, before I start this talk, I'd like to know if anyone is more
confortable with English than French. Ok, so, unless someone here can't
understand English, I'll continue in English, so I can link the video of this
talk in the README of the project I'm going to present you.

2/
My name's Martin, I'm a System & Network engineer at alwaysdata,
a very cool hosting company. Today, I'll present you asynctest, a library which
adds features to the standard package "unittest" to ease testing of asyncio
code. If you're not familiar with asyncio, it's okay: most of the features I'll
talk about exist in unittest, so you can learn useful stuff too.

Who tried or used asyncio? Who writes unit tests?
Great, let's start! I'll try to motivate you to write tests, and present you an
almost real-world example of code to test.


3/
So first: why do we want unit tests?
Unit testing is a bit like practicing sport: at first it's painful to start and
requires a lot of motivation, but once you get used too, you start to enjoy it
and feels its benefits!

4/ You want reliability because reliability is the converse of anxiety: this is
something you want in your daily job. Tests gives you confidence in your work
because it gives you facts showing thay your code works. While coding, tests
detect most obvious mistakes (typos, off-by-one errors, etc). Even better,
tests help to prevent regressions during refactoring. Long story short: tests
will make you to sleep better and fight monstrous old code.

5/ You want consistency: unit tests are your very first occasion to be in the
shoes of the user of your API (package, classes, etc). When testing is hard, it
often means that you can make a better API by reducing coupling and unexpected
side effects (such as changing a value in a getter). For instance, you can do
dependency injection (pass an object you need in parameter rather than creating
it in the function, which gives you a more flexible API).
You will have a chance to see how useable is your API, and have a way to ensure
backward compatibility when updating your code. For that your colleagues and
users will love you and may even buy you beers!

6/ Unittest are also convenient : instead of running on a complex scenario or
check list of cases you have to run manually, everything is automated.
Seriously, writting test takes time, but manual checks or bugs discovered in
production take even more (wasted) time.
One cool stuff is that you won't need to start a large program to test a small
function: you will isolate your code from others' code, and avoid their bugs.

It saves you from toil and boring work: unittest make you like your work again!

7/ Okay, enough small talk, let's show some code!

8/ First, let's see how to organize our tests: we conveniently put them next to
the package to test, and mirror the hierarchy of the package. It allows to
separate the tests from the code, write clean imports in the tests without the
trouble of having to configure the import path (the package is easily found:
it's right there!).

9/ So let's look at network.py, module of the piedpiper package. It contains
a class called ResourceDownloader, with tree functions: get_parsed_url, which
returns split components of an url (host, port, path and if ssl is requested).

download() is a coroutine (an asynchronous function, so to speak) which will
download the resource at the given url.

refresh() allows to set an automatic refresh of the resource every "period"
seconds (so for instance, every five seconds, we will redownload the data. It
can be useful to poll activity, get new messages or whatnot).

10/ now let's test get_parsed_url(): in tests/test_network.py, we create
a new class which inherits from asynctest.TestCase, and define a function
called test_get_parsed_url in which we will put the test.

It's up to you to choose how you want to organize your cases, but I like to
have a class per feature ("functional area"): here, a class per function.

A function defines a case you want to test. Usually, the
function name can be a sentence telling what you test. For instance:
test_get_parsed_url_returns_parsed_url but here it would be redundant.

11/ TestCase provides all you need to run the test, and display the result,
here, we create an instance of test case, the first parameter is the name of
the function which implement the test case we want to run.

Usually, we use a test runner: its a program which uses introspection to find
all the methods with a name starting with test_ in a child of
TestCase, creates an instance for each case, and display a report of the tests
outcome.

12/ Just so you know: this decorator is specific to asynctest: it disables all
sanity checks and features related to asyncio, because get_parsed_url doesn't
require asyncio to run.

13/ Let's look at the content of our test: it's mostly trial: we instanciate
our class, call the method to test, and make a statement about what is required
in order to have a successful test. This is done with the "assert*" methods
provided by Testcase. There are a lot of them. If the assertion is not matched,
an AssertionError is raised and the test fail.
In a test, we should exerce the code with one reprensentation of all the
possible inputs, as we'll see later.

14/ An other example is a test where we check that get_parsed_url raises
a ValueError if the URL can not be parsed. Testing those cases are important:
they show you don't provide inconsistent results and will always raise
a compatible exception (it's part of the API).

15/ Now it's time to run our tests:
This command tells the interpreter where to look for the package, and we invoke
the standard unittest package, which provides a "main" which invokes the test
runner. The last argument in the name of our tests package.

As you can see, when a test fails, a report with the error is printed with the
traceback (and sometimes other informations). The first dot means that the
other test passed without errors.

16/ now, we can test different inputs, but we may duplicate a lot of code, so
let's refactor.

17/ In order to make things more organised, I created a Case type
and listed all the cases to be tested and the expected result in a dict,
indexed with a small description of what the Case wants to test.

18/ We can iterate over the dict without duplicating code. The subtest context
manager allows to identify what case we are testing. If one fails, the report
will output the arguments passed to subTest, providing useful indications about
the location of the failure.

19/ Now, let's see how asynctest helps you with asyncio

20/ We will test download(), which behavior is described in the comments.
We want to test what's in the doc, it is the "contract" between the developer
and the user.

21/ let see how download() works:
    - we parse the URL
    - open a connection to the server
    - send the request
    - read the headers of the response to know the size of the body,
    - read the body
    - close the connection, even if an error happens.

22/ Let's test it!
We simply download a file and check the result. As we see: this is a coroutine
function. Asynctest will create a loop on which the test will run, and close it
once the test finishes.

But something isn't right: what if the server is down or misbehaving?

23/ That's why we need mocks: a mock is an object that conveniently replace
a function, class or object to act like it. We can configure their behavior to
make them behave the way we want. They also register how they were called and
used, so we can assert than a given method has been called with the rights
aruments.

24/ So in our example, we are creating two mock of the reader and writer
objects, we specified which type the mock must mimick, and set the behavior of
two methods of the reader: we simulate a response from the server.

25/ The interface of the reader/writer is preserved, so the mocks will work
with the code of download(). When accessing an attribute of the mock, the value
is itself a mock (reader.read is a mock). When a mock function is called, it
returns a mock, unless we specified a customized return value.

Note that read() and readuntil() are coroutines, and their mocks will behave as
coroutines thanks to asynctest.

26/ Now we need to make sure that open_connection returns our mock objects, we
can achieve this with a patch: a patch is a temporary replacement of a symbol
(here a function in a module) by a mock. In the example, we patch
open_connection so when called, it returns the result of create_mock. Once we
leave the "with" block, the patch is disabled.

27/ Patch can also be used as a function of TestCase decorator. In this case,
it works with coroutines. You can use several types of patches: to patch
several functions of a module, a dict or an object.

Asynctest allows you to patch coroutines with various settings, such as the
scope of activation of the patch (the coroutine may be paused: do we want to
deactivate the patch or wait until the coroutine finishes ?)

28/ Okay, last example now. This one is great: we are going to control time.

29/ But first, let me show you setUp, tearDown and addCleanup. When a test case
run, the setup is first called, allowing to prepare the context of the test.
As you can see: we are going to patch our download method to return a different
result every time (with a counter).

The patch is started at the end of the setup, but we register a cleanup
function: it will be called when the test is finished.

That's also what tearDown does, but tearDown is only called if the test
succeeded, while cleanup functions are always called.
Asynctest allows to make setUp, tearDown and cleanup functions coroutine
functions.

30/ Now let's control time!
Rembember, before, we used a decorator which deactivated some checks. Here, we
add one check: ensure that if something has been scheduled to run on the loop,
it is either done or cancelled. It ensures that we finishes the test in a clean
state.

We schedule refresh every 5 seconds, but we don't want to wait. We use
ClockedTestCase instead of TestCase, which controls the clock of the loop. We
then use advance() to make the time pass. As you see, it really simulates the
time elapsed, instead of "just" changing the clock value.

31/ Okay, we're done!
In the future, I'd like to support some other features of asyncio, such as
async iterators and context managers (async for/async with). I'd like to
provide a complete IO mocking system, you just say what should be ready to be
read and when, and don't mock manually the streams or other functions.
Maybe one day I'll add the support of proactor (for windows), but I don't know
when/how.

If you used pytest-asyncio: it seems to do less things that asynctest, so you
can use the mock module of asynctest with pytest

If you wonder who uses asynctest. So far -not to brag- I heard from people at
mozilla and cisco use it.

32/ Now it's your turn to write unittest. Just a small tip: in your open source
project, think about telling how users and contributors are expected to run the
tests. It should be as easy as a simple command: don't require complex manual
setup, or they won't be used. Plus, if everything is automated, you can enable
continuous integration!

from riot import Suite, Case


suites = [
    Suite(
        name="test_nocmdargs",
        command="echo no cmdargs",
        cases=[
            Case(
                pys=[3.8],
            ),
        ],
    ),
    Suite(
        name="test_cmdargs",
        command="echo cmdargs={cmdargs}",
        cases=[
            Case(
                pys=[3.8],
            ),
        ],
    ),
]

# coding=utf-8

"""
    This file is used to run nosetests with coverage:
    coverage run -p --source=frontik -m tests

    Then after all .coverage* files are created:
    coverage combine ; coverage report
"""

if __name__ == '__main__':
    import nose
    nose.main(argv=['nosetests', 'tests/', '-v'])

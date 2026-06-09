# buwizz-pro3-bluetooth-python

BuWizz Pro 3 Lego controller python bluetooth library based on bleak

> NOTE: Intentionally long and specific name so BuWizz have rights to a more abstract concise named library


<!--TOC-->

- [buwizz-pro3-bluetooth-python](#buwizz-pro3-bluetooth-python)
- [Quickstart](#quickstart)
- [User Guide](#user-guide)
- [Publishing](#publishing)
- [Contributing](#contributing)
- [TODO](#todo)

<!--TOC-->

# Quickstart

tbd

----

# User Guide

tbd

----

# Publishing

To publish a new version create a release from `main` (after pull request).

# Contributing

At all times, you have the power to fork this project, make changes as you see fit and then:

```sh
pip install https://github.com/user/repository/archive/branch.zip
```
[Stackoverflow: pip install from github branch](https://stackoverflow.com/a/24811490/622276)

That way you can run from your own custom fork in the interim or even in-house your work and simply use this project as a starting point. That is totally ok.

However if you would like to contribute your changes back, then open a Pull Request "across forks".

Once your changes are merged and published you can revert to the canonical version of `pip install`ing this package.

If you're not sure how to make changes or _if_ you should sink the time and effort, then open an Issue instead and we can have a chat to triage the issue.


# TODO
 - Get `bleak` to talk to BuWizz controller https://github.com/hbldh/bleak/blob/master/examples/uart_service.py
 - Setup a BLE Profile similar to what PyBricks has done https://github.com/pybricks/pybricksdev/blob/master/pybricksdev/ble/pybricks.py
 - Also the Nordic UART Service (NUS) https://github.com/pybricks/pybricksdev/blob/master/pybricksdev/ble/nus.py
 - Take inspiration from Lego Wire Protocol 3 LWP3 on how to read/write over UART https://github.com/pybricks/pybricksdev/blob/master/pybricksdev/ble/lwp3/messages.py
 - Get MKDocs docs to auto generate based on code API.
   - Investigate these https://facelessuser.github.io/pymdown-extensions/
   
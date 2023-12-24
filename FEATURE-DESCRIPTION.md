# Objective:
Enhance Augratin by integrating a feature to broadcast POTA QSOs using UDP when the ‘log it’ button is activated.

# Approach:
Using Port 2333 to send which is the same port as WSJT-X. Figured with the popularity of WSJT-X, most logging software would most likely have builtin capability to listen for adif data on that part (I know HRD does) Probably not a scenario where Augratin and WSTJ-TX would be useds simultaineosly - May rethink this but there is the option to force a different UDP server address in the args. 

# Dev Notes
this branch also has some configuration files for setting up a devcontainer for vscode. Never did this before and used this as a learning opportunity. Probably made it way over complicated. It did take me two days to figure out how to set up the environment and 20 min. to code the added function....


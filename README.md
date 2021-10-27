# Trading platform PoC

A POC for the trading platform system including agents and market solver.

## Agents
Info about agent design

## Market solver
Info about market solver design


# Merge strategy
The general strategy is to work on separate branches and make a merge request in gitlab to merge into master.

When starting work on a new feature, create a new branch. In bash, that looks like this:

     git checkout -b "branch-name"
If there is a ticket number associated with the work, that is good to include in the branch name.

Proceed to write your code and commit your work, and when it's done and ready to merge you push the new branch to origin in order to initiate the merge request. In bash, that looks like this:

    git push -u origin branch-name
Then go to gitlab in your browser and complete the merge request there.

It can also be a good idea to switch back to master and do a git pull there before pusing, and merging any updates locally. This prevents merge conflicts in the pull request.
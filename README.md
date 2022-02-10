[![pipeline status](https://gitlab01.afdrift.se/futuretechnologies/tornet-jonstaka/trading-platform-poc/badges/main/pipeline.svg)](https://gitlab01.afdrift.se/futuretechnologies/tornet-jonstaka/trading-platform-poc/commits/main)
[![coverage report](https://gitlab01.afdrift.se/futuretechnologies/tornet-jonstaka/trading-platform-poc/badges/main/coverage.svg)](https://gitlab01.afdrift.se/futuretechnologies/tornet-jonstaka/trading-platform-poc/commits/main)

# Trading platform PoC

A POC for the trading platform system including agents and market solver.

## Preliminaries
Tested on:
- Ubuntu 18.04, bionic using Python=3.9.4
  - Compatible with tox for code quality checks and running tests

          sudo apt update
          sudo apt install tox
- Windows OS ?

## Setup a virtual environment
Consider setting up a virtual environment for the repository. Use conda, or venv as follows:

        virtualenv -p python3.9.4 venv

*Note:* don't forget to activate the virtual environment. Depending on your IDE, you can probably choose to set the 
default interpretor to your venv.

## Install dependencies

        pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
        pip install -r requirements-test.txt

Install package as editable (command automatically searches for the setup.py file): 
        
        pip install -e .

## Generate mock data
* Verify that you have a json config file under the data folder specifying the area to be simulated.
* Run the mock data generation script:

        python scripts/generate_mock_data.py

The resulting data is stored in a pickle file. To verify its contents, save an extract in a .csv file using the 
[extraction script](scripts/extract_df_from_mock_datas_pickle_file.py).
## Run POC

### As script from terminal
From the root of the repository, run the main file:

        python main.py

This will populate the results folder with outputs. In addition, a [log file](trading-platform-poc.log) is generated and stored in the repository root.
### As docker container
Install Docker (verify installation by running "docker run hello-world"). Navigate to the root of the trading 
platform-poc repository; build a docker image based on the Dockerfile

## Streamlit GUI
To run the streamlit GUI, make sure streamlit and altair are installed in your venv

    pip install streamlit
    pip install altair

Then, to run the gui:

    streamlit run app.py

For inspiration on further improvements on the gui, check out:

https://awesome-streamlit.org/

and the source repo:

https://github.com/aliavni/awesome-data-explorer

        docker build -t imagename .

where the -t flag allows you to specify an image name (imagename). Once built, instantiate (and run) a docker container 
based on the created image

        docker run imagename:latest

Once the container has run, the logger information relating to the job can be accessed at a later time by identifying 
the containerID (see below for how to do this), and reviewing its logs

        docker logs containerID

#### Docker Ecosystem Basics
For a basic overview of Docker, see https://docker-curriculum.com/.
- *image*: the blueprint of the container/application.
- *container*: Instantiation image and run of application.
- *Dockerfile*: text file containing the commands to creating an image.

To delete a container and avoid stray containers from occupying disk space, remove it as

        docker rm containerID

where the containerID can be identified from

        docker ps -a

which returns a list of the containers that have run. To delete all completed containers, run

        docker container prune


# Specs. on system architecture 
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
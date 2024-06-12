# Energy trading simulator

This projects simulates energy trades within a local energy community (LEC).
It has been developed for a research project funded by Energimyndigheten,
focusing on a planned development by Tornet Bostadsproduktion AB, at Jonstaka in Varberg, Sweden.

To work on this code, ensure you are running **python 3.9**, and install the dependencies necessary:

        pip install -r requirements.txt
        pip install -r requirements-dev.txt
        pip install -r requirements-test.txt

To run the code, you also need to set up a PostgreSQL database. At AFRY, we have set up such a database in Azure.
Wherever you host it, fill in the appropriate environment variables... ↓

### Environment variables
Several environment variables are required to make the code run properly.
These can be set in a file named ".env", placed in the project root.

    PG_USER
    PG_HOST
    PG_DATABASE
    PG_DATABASE_TEST
    PG_PASSWORD
    GLPK_PATH

#### PG_...
The variables prefixed by "PG_" specify attributes of the associated PostgreSQL database.

Examples:

    PG_USER = "jonstaka_python"
    PG_HOST = "DATABASE_NAME.postgres.database.azure.com"
    PG_DATABASE = "jonstaka_local"
    PG_DATABASE_TEST = "jonstaka_test"
    PG_PASSWORD = "REDACTED, obviously"

#### GLPK_PATH
This variable is needed for the optimization stage, but only if you are **not** on a Linux system.
If you are on Linux, you just need to install GLPK (this is done when running the project as a Docker container, too).

But on other operating systems, e.g. Windows, this variable should specify the path to where you have the "glpsol.exe" file.

For example:

    GLPK_PATH=C:\...\glpk-4.65\w64\glpsol

### Test mode
When developing and testing, it saves a lot of time to not run the full year of simulations.
This can be achieved by setting an environment variable named "NOT_FULL_YEAR" to "True".

## Creating a release
1. Ensure that your local main and develop branches are up-to-date
2. Checkout develop branch
3. If you haven't done any git flow operations on this project, you will have to run "git flow init" - you will be asked a bunch of questions, and you should just accept the default answers (by pressing enter)
4. Run "git flow release start TAG_NAME" where TAG_NAME is the tag identifier, for example 1.0.2
5. Change version in the files where its needed (at time of writing setup.py and footer.py, but it is probably easiest to do a Replace All), commit the change (this ensures that the proper version is shown in the UI)
6. Run "git flow release finish TAG_NAME"
   * You'll be prompted to enter a tag message (similar to a commit message) in whatever text editor you have set as git's default, or probably Vim if you haven't set anything
7. Push the tag, and the updated develop and main branches: "git push origin TAG_NAME; git push origin develop; git push origin main"

Steps 8-9 are only relevant if you are running the app in Azure (more on that further down below). If you are not, skip to 10.

8. Pushing the tag will trigger 2 "extra" GitHub **Actions**:
   1. release - creates a release in GitHub
   2. deploy - builds a Docker image and pushes it to the Azure Container Registry, with the tag name being the same as the git tag name. (Note that this uses an Azure service principal, for which login credentials have been added as "secrets" to the GitHub repository)
      1. This will occasionally produce an error: Error response from daemon: Get "https://CONTAINER_REG_NAME.azurecr.io/v2/": unauthorized: Invalid clientid or client secret
      2. This is likely due to the fact that the service principal's certificate has expired
      3. If so - go to it. If you type "service principal" at the top of the Azure interface, you may see it, otherwise, this link may work
      4. If the certificate indeed has expired, it will clearly say "A certificate or secret has expired. Create a new one →" in red.
      5. Click this, generate a new certificate, copy the Value
      6. Go to the GitHub repository, click "Settings → Secrets and variables → Actions"
      7. Edit "AZURE_PASSWORD", paste the Value
      8. Re-run the "deploy" stage
9. To apply the changes to the web app, open the App Service, click "Deployment Center", and choose the appropriate "Tag" from the dropdown. This will restart the App Service with the specified version. 
10. On develop, you may want to change the version numbers (as you did in step 5) to a ".dev"-name. For example, if you just released version 1.0.2, the version numbers on develop should probably be "1.0.3.dev".

If you would like to tag a temporary branch, just to test how something works in Azure (such as testing runtimes):

1. checkout the branch you want to test
2. git tag TAG_NAME
3. git push origin TAG_NAME

Change the tag in Azure / App Service / Deployment Center. When you are done testing, the tag can be removed by running "git push --delete origin TAG_NAME ; git tag -d TAG_NAME" (the first command deletes it from the remote, and the second command deletes it locally).

## Access Azure Database through pgAdmin
The following guide is for using pgAdmin to access the Azure Database, but this is optional, and you can choose GUI after your liking.

Make sure you have an active subscription on Azure and access to the relevant Resource group: _JonstakaPOC_.
Make sure pgAdmin is installed and setup with password (personal, will not affect the access of others).
Make sure your ip address is in JonstakaPOC/database_jonstaka/Networking. 

To access the server:

- Right click Server in the left drop down menu in pgAdmin and choose Register -> Server...
- Under the General tab fill Name (of your choosing).
- Under the Connection tab add info from _JonstakaPOC_ in Azure:
  - _Host name/adress_: Corresponds to the Server name in the Database Overview.
  - _Username_: Here use the Admin username in the Database Overview. (everything before the @)
  - _Password_: This is found in Key vault -> Secrets. Copy the CURRENT VERSION of the admin password and Save.
  - Save the password in pdAdmin. 

NOTE: Do not use admin user with python.

## Run the GUI
To run the streamlit GUI, make sure streamlit and altair are installed in your environment 
(they will be, if you installed requirements.txt)

    pip install streamlit
    pip install altair

Then, to run the gui:

    streamlit run app.py

For inspiration on further improvements on the GUI, check out:

https://awesome-streamlit.org/

and the source repo:

https://github.com/aliavni/awesome-data-explorer

### Run simulation without GUI

From the root of the repository, run the main file:

        python main.py

This will populate the results folder with outputs. In addition, a [log file](logfiles/trading-platform-poc.log) is 
generated and stored in the "logfiles" directory.

### As a Docker container
Install Docker (verify installation by running "docker run hello-world"). Navigate to the root of the trading 
platform-poc repository; build a docker image based on the Dockerfile

        docker build -t imagename .

where the -t flag allows you to specify an image name (imagename). Once built, instantiate (and run) a docker container 
based on the created image

        docker run -p 8880:80 imagename:latest

Here, 8880:80 maps the local port 8880 to the container's port 80. Therefore, one can navigate to localhost:8880 in
one's browser, and this should display the Streamlit GUI.

Once the container has run, the logger information relating to the job can be accessed at a later time by identifying 
the containerID (see below for how to do this), and reviewing its logs

        docker logs containerID

### Running the app in Azure
Since May 2022, AFRY are running this web app in Azure. Ownership of this will be transferred to Chalmers in June 2024.

To update the version of the app in Azure, follow the steps below.

This assumes that the app is owned by a subscription named "subscription_name",
situated in a resource group named "resource_group_name"
and that the container registry which holds the Docker images is named "container_reg_name"

1. Make sure you have Azure CLI installed
2. Make sure you have access to the Azure subscription in which the app lives
   1. If you aren't already on that subscription, switch to it by running "az account set --subscription "subscription_name"" (replace "subscription_name")
3. Navigate to the project root folder
4. Run the following command: "az acr build --registry container_reg_name --resource-group resource_group_name --image tppoc-app ."
5. When the above command has finished:
   1. Navigate to the App Service in the Azure portal.
   2. Click "Deployment Center" on the left
   3. Check the "Tag" dropdown. If this is set to "latest", you just need to restart the app, and the latest image will be used. If a specific image name is selected, choose the one you want. The app will restart if you change version, so no need to do so explicitly.
   4. Go to the app URL, ensure that the proper version is running by checking the page footer, where the version number should be located (but it will take a little while to start up)

#### Logs
Logs are currently (as of May 2024) being saved to a storage account named "jonstakalogstorage".
The setup for this is handled under "Diagnostic settings" in the App Service page in the Azure portal.
Logs are retained for 7 days.
"AppServiceConsoleLogs" is the output from the container, i.e. the logs that we most often are interested in.
In "AppServiceHttpLogs" we can monitor traffic to the app.
To examine the logs in the storage account, either use the Azure portal, or install "Microsoft Azure Storage Explorer", and connect to the storage account using an access key, which you can find by navigating to the storage account in the Azure portal.

You can also view the logs by clicking "Log stream" in the App Service page in Azure Portal. This works automatically: Any information written to files ending in .txt, .log, or .htm that are stored in the /logfiles directory is streamed by App Service.

The best way (arguably) of viewing logs, though, is in the log analytics workspace. This is accessed through the "Logs" tab in the App Service page. Here, you can search through logs, create alerts, etcetera.

For more information, see https://docs.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs.
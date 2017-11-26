# Kispagi
Kispagi (which means to pay with kisses in Esperanto) is an app that connects to your favourite(s) issue tracker or project manager(Gitlab, etc) to calculate the contributed hours and calculate a payment distribution with different rules.

## How to install it
    git clone git@github.com:capiscuas/kispagi.git kispagi
    cd kispagi

### Create a python virtualenv
    export LC_ALL=C # in case you get error when creating the virtualenv
    #For python3
    virtualenv -p /usr/bin/python3 venv
    #For python2
    virtualenv -p /usr/bin/python2 venv
    source venv/bin/activate #to enter in the virtualenv

### Installing Requirements
    pip install flask requests python-dateutil python-slugify

### Configuring settings
Create a file **env/settings.py** which will contain the following content:

    ocp_token = "REPLACE_BY_THE_VALUENETWORK USER TOKEN"
    ocp_host = "REPLACE BY THE VALUENETWORK GRAPHEN API URL"
    gitlab_host = 'GITLAB API URL'
    gitlab_token = 'GITLAB USER TOKEN'

### Running
    cd flask_app
> **Note:**
> Make sure you have the virtual environment activated


    python flask_app.py
Then open your browser at http://127.0.0.1:5000/

## Supported platforms
### Valuenetwork
* [<i class="icon-refresh"></i> Repository](https://github.com/FreedomCoop/valuenetwork/)
### Gitlab
* [<i class="icon-file"></i> Website](https://about.gitlab.com/)

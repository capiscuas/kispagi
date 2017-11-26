# kispagi
Kispagi (which means to pay with kisses in Esperanto) is an app that connects to your favourite(s) issue tracker or project manager(gitlab, etc) to calculate the contributed hours and calculate a payment distribution with different rules.


#How to install it
git clone git@github.com:capiscuas/kispagi.git kispagi
cd kispagi
###Create a python virtualenv
    export LC_ALL=C # in case you get error when creating the virtualenv
    #For python3
    virtualenv -p /usr/bin/python3 venv
    #For python2
    virtualenv -p /usr/bin/python2 venv
    source venv/bin/activate #to enter in the virtualenv

###Installing Requirements
    pip install flask requests python-dateutil python-slugify

###Running
    cd flask_app
> **Note:**
> Make sure you have the virtual environment activated


    python flask_app.py
Then open your browser at http://127.0.0.1:5000/

###Notes
> **Supported platforms:**

> - [<i class="icon-refresh"></i> Valuenetworks](https://github.com/FreedomCoop/valuenetwork/)
> - [<i class="icon-file"></i> Gitlab](https://about.gitlab.com/)

import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
import uuid


from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")



#TODO Complete the implementation of index in such a way that it displays an HTML table summarizing, 
# for the user currently logged in, which stocks the user owns, the numbers of shares owned, the current 
# price of each stock, and the total value of each holding (i.e., shares times price). Also display the 
# user’s current cash balance along with a grand total (i.e., stocks' total value plus cash).

#for each user:
#stocks user owns, 
#amount of share in that stock, 
#current price of the stock, 
#total value of the holding, 
#users cash balance, 
#grand total(stock value + total cash) this uses current costs i.e. use lookup

@app.route("/", methods=['GET'])
@login_required
def index():
    user = db.execute("select distinct cash, symbol, sum(shareAmount), sum(shareCost) from users left join userstocks on users.id = userstocks.user left join transactions on userstocks.transactionID = transactions.id where users.id=:userID and transactionType='purchase' group by symbol", userID = session['user_id'])
    holdingsTotal = 0
    if user[0]['sum(shareAmount)'] != None:
        for i in user:
            curr_stock = lookup(i['symbol'])
            curr_price = curr_stock['price']
            holdingsTotal += curr_price * i['sum(shareAmount)']
        holdingsTotal += user[0]['cash']
    return render_template('index.html', total_holdings=float(holdingsTotal), data=user, cash=float(user[0]['cash']))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == 'GET':
        return render_template('buy.html', bought=False)

    elif request.form.get('symbol') and request.form.get('shareAmount') != None:
        funds = db.execute("select cash from users where id= :id", id = session.get("user_id"))
        share = lookup(request.form.get('symbol'))
        costPerShare = share['price']

        if share == None:
           return apology("That share doesn't exist.")

        elif (costPerShare * int(request.form.get('shareAmount'))) < float(funds[0]['cash']):
            #Add purchase to purchases DB, USing user id as link
            uid = uuid.uuid4()
            db.execute("insert into transactions (id, transactionType, symbol, shareAmount, user, shareCost, date) values (:id 'purchase', :symbol, :share_amount, :user, :costPerShare, datetime('now'))", id=uid,
            symbol=request.form.get('symbol'), share_amount=int(request.form.get('shareAmount')), user=session.get('user_id'), costPerShare = int(costPerShare))

            db.execute("insert into userstocks (user, transactionID) values (:user, :transactionID)", user=session.get('user_id'), transactionID=uid)

            db.execute("update users set cash=:cash where id=:userid", cash=float(funds[0]['cash']) - (costPerShare * int(request.form.get('shareAmount'))), userid=session.get("user_id"))

            return render_template('buy.html', bought=True, data=(request.form.get('shareAmount'), request.form.get('symbol'), share['price']))

    return apology("Error, Please try again.")


@app.route("/history")
@login_required
def history():
    allTransactions = db.execute("select * from transactions inner joinwhere user=:userID", userID=session['user_id'])
    if allTransactions:
        return render_template('history.html', data=allTransactions)
    return apology("You have no transactions!")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == 'GET':
        return render_template('quote.html')
    elif request.form.get('symbol') and lookup(request.form.get('symbol')) != None:
        return render_template('quoted.html', data=lookup(request.form.get('symbol')))
    else:
        return apology("Invalid Stock Symbol", 403)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == 'GET':
        return render_template('register.html')
    elif request.form['username'] and request.form['password'] and request.form['confirmation'] and (request.form['password'] == request.form['confirmation']):
        if len(db.execute("select * from users where username = :username", username=request.form.get("username"))) != 1:
            hashPW = generate_password_hash(request.form['password'], method='pbkdf2:sha256', salt_length=8)
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"), hash=hashPW)
            return redirect('/login')
    #else:
    #    return apology("Username, Password or confitmation incorrect, Please try again!", 403)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == 'GET':
        return render_template('buy.html')
    elif request.form.get('symbol') and request.form.get('numberOfShares') != None and request.form.get('numberOfShares') > 0:
        usersStocks = db.execute("select distinct sum(shareAmount), symbol from transactions where user=:userID and where symbol=:symbol and where transactionType='purchase' group by symbol", userID=session['user_id'], symbol=request.form.get('symbol'))
        if usersStocks != None and usersStocks['sum(shareAmount)'] >= request.form.get('numberOfShares'):
            stock = lookup(request.form.get('symbol'))
            stockPrice = stock['price']

    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

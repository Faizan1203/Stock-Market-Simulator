import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

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

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = db.execute(
        "SELECT stock_name, stock_symbol, stock_qty, stock_price, stock_total FROM stock WHERE users_id = ?", session["user_id"])
    userscash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = userscash[0]["cash"]

    grandtotal = 0
    if stocks is not None:
        for stock in stocks:
            symbol = stock["stock_symbol"]
            shares = stock["stock_qty"]
            name = stock["stock_name"]
            price = lookup(symbol)["price"]
            total = shares * lookup(symbol)["price"]
            grandtotal += total
            db.execute("UPDATE stock SET stock_price = ?, stock_total = ? WHERE users_id = ? AND stock_symbol = ?",
                       price, total, session["user_id"], symbol)

        grandtotal += cash
        return render_template("index.html", stocks=stocks, grandtotal=grandtotal, cash=cash)
    else:
        return render_template("index.html", cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "GET":
        return render_template("buy.html")

    elif request.method == "POST":
        symbol = request.form.get("symbol").upper()
        sharesin = (request.form.get("shares"))
        lookedupsymbol = lookup(symbol)
        user = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = user[0]["cash"]
        if not symbol:
            return apology("INVALID SHARES/SYMBOLS", 400)

        elif lookedupsymbol == None:
            return apology("INVALID SHARES/SYMBOLS", 400)

        elif not sharesin:
            return apology("INVALID SHARES/SYMBOLS", 400)

        shares = int(sharesin)

        try:
            shares = int(shares)
        except:
            return apology("shares must be a positive integer")

        if shares < 1:
            return apology("INVALID SHARES/SYMBOLS", 400)

        elif (lookedupsymbol["price"] * float(shares)) > cash:
            return apology("NOT ENOUGH FUNDS", 400)

        stocks = db.execute("SELECT stock_qty FROM stock WHERE users_id = ? AND stock_symbol = ?", session["user_id"], symbol)

        if lookedupsymbol != None:
            cash = cash - (lookedupsymbol["price"] * float(shares))

            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])

            if stocks:

                shares_total = shares + stocks[0]["stock_qty"]

                total = lookedupsymbol["price"] * shares

                db.execute("UPDATE stock SET stock_qty = ?, stock_price = ?, stock_total = ? WHERE users_id = ? and stock_symbol = ?" ,
                           shares_total, lookedupsymbol["price"], shares_total * lookedupsymbol["price"], session["user_id"], symbol)

            else:
                total = lookedupsymbol["price"] * float(shares)

                db.execute("INSERT INTO stock (users_id, stock_symbol, stock_qty, stock_price, stock_name, stock_total) VALUES (?, ?, ?, ?, ?, ?)",
                           session["user_id"], symbol, shares, lookedupsymbol["price"], lookedupsymbol["name"], total)

            db.execute("INSERT INTO stock_buy_history (users_id, stock_symbol, stock_qty, stock_price, stock_name, time_stamp_bought) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                           session["user_id"], symbol, shares, lookedupsymbol["price"], lookedupsymbol["name"])

        flash("BOUGHT!")

        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    stocks_bought = db.execute(
        "SELECT stock_name, stock_symbol, stock_qty, stock_price, stock_name, time_stamp_bought FROM stock_buy_history WHERE users_id = ?", session["user_id"])

    stocks_sold = db.execute(
        "SELECT stock_name, stock_symbol, stock_qty, stock_price, stock_name, time_stamp_sold FROM stock_sell_history WHERE users_id = ?", session["user_id"])

    if stocks_bought is not None or stocks_sold is not None:
        return render_template("history.html", stocks_bought=stocks_bought, stocks_sold=stocks_sold)

    else:
        return render_template("history.html")


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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
    """Get stock quote."""

    if request.method == "GET":
        return render_template("quote.html")

    elif request.method == "POST":
        symbol = request.form.get("symbol").upper()
        lookedupsymbol = lookup(symbol)
        if not symbol:
            return apology("MISSING STOCK NAME")
        elif lookup(symbol) != None:
            return render_template("quoted.html", sym=lookedupsymbol)
        else:
            return apology("Invalid Stock name")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    password = request.form.get("password")
    username = request.form.get("username")
    confirmation = request.form.get("confirmation")
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confo was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation password", 400)

        elif password != confirmation:
            return apology("Passwords don't match")

        if password == confirmation:

            hashvalue = generate_password_hash(request.form.get("password"))

        try:
            prim_key = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashvalue)
        except:
            return apology("username already taken", 400)

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stocks = db.execute(
        "SELECT stock_symbol, SUM(stock_qty) AS stock_qty FROM stock WHERE users_id = ? GROUP BY stock_symbol", session["user_id"])
    user = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = user[0]["cash"]

    if request.method == "GET":
        return render_template("sell.html", stocks=stocks)

    elif request.method == "POST":
        sharesin = (request.form.get("shares"))
        symbolin = request.form.get("symbol")

        if not symbolin:
            return apology("INVALID STOCK SYMBOL")

        symbol = symbolin.upper()
        lookedupsymbol = lookup(symbol)
        price = lookedupsymbol["price"]

        if not sharesin:
            return apology("INVALID SHARES")

        shares = int(sharesin)

        users_stock_qty = db.execute(
            "SELECT SUM(stock_qty) as total_shares FROM stock WHERE stock_symbol = ? AND users_id = ?", symbol, session["user_id"])

        if not users_stock_qty or int(users_stock_qty[0]["total_shares"]) < shares:
            return apology("NOT ENOUGH SHARES")

        shares_total = users_stock_qty[0]["total_shares"] - shares

        total = price * shares_total

        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", price * shares, session["user_id"])

        db.execute("INSERT INTO stock_sell_history (users_id, stock_symbol, stock_qty, stock_price, stock_name, time_stamp_sold) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                   session["user_id"], symbol, shares, price, lookedupsymbol["name"])

        if shares_total == 0:
            db.execute("DELETE FROM stock WHERE stock_symbol = ? AND users_id = ?", symbol, session["user_id"])

        else:
            db.execute("UPDATE stock SET stock_qty = ?, stock_total = ? WHERE users_id = ? AND stock_symbol = ?",
                       shares_total, total, session["user_id"], symbol)

        flash("Sold!")
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

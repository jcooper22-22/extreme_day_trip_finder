from flask import redirect, url_for
from flask import Flask, render_template, request
from main import extreme_day_trip_finder
from main import get_ryanair_airports
from main import get_iata
from flask import session
from math import ceil

app = Flask(__name__)
app.secret_key = "xxxx"


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":
        origin_name = request.form.get("originCity")
        budget = request.form.get("budget")

        date_start = request.form.get("date_start")
        date_end = request.form.get("date_end")

        iata = get_iata(origin_name, "airports.csv")

        results_dict = extreme_day_trip_finder(
            iata, budget, date_start, date_end)
        session["flight_results"] = results_dict
        return redirect(url_for("search", page=1))

    ryanair_airports = get_ryanair_airports(
        "ryanair_airports.csv", "airports.csv")

    return render_template("index.html", ryanair_airports=ryanair_airports)


@app.route("/search")
def search():

    page = int(request.args.get("page", 1))

    results = session.get("flight_results", [])
    per_page = 10
    results_list = list(results.items())
    shown = results_list[(page-1) * per_page: (page) * per_page]

    return render_template("result.html", results=shown, page=page, total_pages=ceil(len(results)/10))


@app.template_filter('sort_by_price')
def sort_by_price_filter(value):
    return sorted(value, key=lambda x: x[1]["price"])


if __name__ == "__main__":
    app.run(debug=True)

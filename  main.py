import requests
from datetime import datetime, timedelta
import csv


def get_ryanair_flights(origin_iata, start_date, end_date, currency):
    """
    Fetch the cheapest one-way Ryanair fares from a given origin airport 
    for all destinations within a specified date range.

    This function queries the Ryanair public API for each day between 
    `start_date` and `end_date` and returns a list of fares, as this returns more results.

    Args:
        origin_iata (str): IATA code of the origin airport (e.g., "STN").
        start_date (str): Start date in "YYYY-MM-DD" format.
        end_date (str): End date in "YYYY-MM-DD" format.
        currency (str): Currency code for prices (e.g., "EUR", "GBP").

    Returns:
        list: A list of fare objects returned by the Ryanair API. 
              Each item typically contains:
              - `outbound` (dict): Departure/arrival airport and time.
              - `summary` (dict): Price and fare details.

    Raises:
        requests.exceptions.RequestException: If the API request fails.
        ValueError: If the date format is invalid.
    """
    url = "https://www.ryanair.com/api/farfnd/3/oneWayFares"

    params = {
        "departureAirportIataCode": origin_iata,
        "outboundDepartureDateFrom": start_date,
        "outboundDepartureDateTo": end_date,
        "currency": currency
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }

    current_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    all_fares = []

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")

        url = "https://www.ryanair.com/api/farfnd/v4/oneWayFares"
        params = {
            "departureAirportIataCode": origin_iata,
            "outboundDepartureDateFrom": date_str,
            "outboundDepartureDateTo": date_str,
            "market": "en-gb"
        }
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            all_fares += response.json().get("fares", [])
        except Exception as e:
            print(f"Error fetching fares for {date_str}: {e}")

        current_date += timedelta(days=1)

    return all_fares


def get_singular_ryanair_return_flight(departure_flight, currency):
    """
    Finds a single suitable return flight from Ryanair for a given outbound flight.

    Parameters:
        departure_flight (dict): Dictionary containing outbound flight details, 
                                 expected to have keys:
                                 - 'outbound' -> 'arrivalDate' (str, ISO format)
                                 - 'outbound' -> 'departureDate' (str, ISO format)
                                 - 'outbound' -> 'departureAirport' -> 'iataCode' (str)
                                 - 'outbound' -> 'arrivalAirport' -> 'iataCode' (str)
        currency (str): Currency code for flight prices (e.g., "EUR", "GBP").

    Returns:
        dict or None: The first matching return flight as a dictionary if found, 
                      or None if no suitable return flight is available.

    Notes:
        - Only considers return flights on the same day as the arrival of the outbound flight.
        - Filters for return flights departing at least 6 hours after the outbound arrival.
        - If the API returns a 400 error or no flights are found, returns None.
    """

    arrival_date_outbound = departure_flight["outbound"]["arrivalDate"]
    date_only = datetime.strptime(
        arrival_date_outbound, "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d")
    departure_outbound_time = datetime.strptime(
        departure_flight["outbound"]["departureDate"], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d")
    if departure_outbound_time != date_only:
        return None

    dt = datetime.strptime(arrival_date_outbound, "%Y-%m-%dT%H:%M:%S")

    min_time_raw = dt + timedelta(hours=6)
    max_time_raw = dt.replace(hour=23, minute=59, second=59)

    destination_iata = departure_flight["outbound"]["departureAirport"]["iataCode"]
    origin_iata = departure_flight["outbound"]["arrivalAirport"]["iataCode"]

    url = "https://www.ryanair.com/api/farfnd/3/oneWayFares"
    params = {
        "departureAirportIataCode": origin_iata,
        "arrivalAirportIataCode": destination_iata,
        "outboundDepartureDateFrom": date_only,
        "outboundDepartureDateTo": date_only,
        "currency": currency
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 400:
        return None

    try:
        return response.json()["fares"][0]
    except:
        return None


def find_suitable_flights(departure_flight):
    """
    Finds a suitable return flight for a given outbound Ryanair flight and calculates the total price.

    Parameters:
        departure_flight (dict): Dictionary containing outbound flight details, expected to have keys:
                                 - 'outbound' -> 'departureAirport' -> 'iataCode', 'name'
                                 - 'outbound' -> 'arrivalAirport' -> 'iataCode', 'name'
                                 - 'outbound' -> 'departureDate' (str, ISO format)
                                 - 'outbound' -> 'arrivalDate' (str, ISO format)
                                 - 'outbound' -> 'price' -> 'value', 'currencyCode'

    Returns:
        tuple or None: A tuple (departure_flight, return_flight, total_price) if a suitable return flight is found,
                       where total_price is the sum of the outbound and return flight prices. 
                       Returns None if:
                           - No suitable return flight is found
                           - The layover between outbound arrival and return departure is less than 4 hours

    Notes:
        - Uses `get_singular_ryanair_return_flight` to fetch the return flight.
        - Assumes currency conversion or consistency is handled outside this function.
        - Calculates layover in hours to filter flights that are too close.
    """

    origin_iata = departure_flight["outbound"]["departureAirport"]["iataCode"]
    origin_name = departure_flight["outbound"]["departureAirport"]["name"]
    destination_iata = departure_flight["outbound"]["arrivalAirport"]["iataCode"]
    destination_name = departure_flight["outbound"]["departureAirport"]["name"]

    departure_date_depart = departure_flight["outbound"]["departureDate"]
    arrival_date_depart = departure_flight["outbound"]["arrivalDate"]
    price_departure = departure_flight["outbound"]["price"]["value"]
    currency = departure_flight["outbound"]["price"]["currencyCode"]

    return_flight = get_singular_ryanair_return_flight(departure_flight, "EUR")
    if return_flight is None:
        return None

    departure_date_return = return_flight["outbound"]["departureDate"]
    arrival_date_return = return_flight["outbound"]["arrivalDate"]
    price_return = return_flight["outbound"]["price"]["value"]
    currency = return_flight["outbound"]["price"]["currencyCode"]

    dt1 = datetime.fromisoformat(arrival_date_depart)
    dt2 = datetime.fromisoformat(departure_date_return)
    delta = dt2 - dt1
    difference = delta.total_seconds() / 3600
    if difference < 4:
        return None

    total_price = price_departure + price_return
    return departure_flight, return_flight, total_price


def extreme_day_trip_finder(origin_iata, budget, date_start, date_end):
    """
    Finds all suitable one-day round-trip Ryanair flights from a given origin within a specified date range and budget.

    Parameters:
        origin_iata (str): IATA code of the departure airport.
        budget (float or str): Maximum total price for the round trip.
        date_start (str): Start date for searching flights in "YYYY-MM-DD" format.
        date_end (str): End date for searching flights in "YYYY-MM-DD" format.

    Returns:
        dict: A dictionary keyed by destination airport names, where each value is another dictionary containing:
            - "departures": outbound flight information (dict)
            - "returns": return flight information (dict)
            - "price": total round-trip price (float, rounded to 2 decimal places)

        The dictionary is sorted by total price in ascending order.

    Notes:
        - Uses `get_ryanair_flights` to fetch outbound flights.
        - Uses `find_suitable_flights` to find matching return flights on the same day.
        - Filters out flights exceeding the budget or with unsuitable layover times.
        - Dates in the returned dictionary are formatted using `nice_date_format`.
        - Prints flight details and total flights found for debugging/inspection.
    """

    total = 0

    record = get_ryanair_flights(origin_iata, date_start, date_end, "GBP")
    actual_dict = {}
    for departure_flight in record:

        origin_iata = departure_flight["outbound"]["departureAirport"]["iataCode"]
        origin_name = departure_flight["outbound"]["departureAirport"]["name"]
        destination_iata = departure_flight["outbound"]["arrivalAirport"]["iataCode"]
        destination_name = departure_flight["outbound"]["arrivalAirport"]["name"]

        departure_date_depart = departure_flight["outbound"]["departureDate"]
        arrival_date_depart = departure_flight["outbound"]["arrivalDate"]
        price_departure = departure_flight["outbound"]["price"]["value"]
        currency = departure_flight["outbound"]["price"]["currencyCode"]

        result = find_suitable_flights(departure_flight)

        departure_date_depart = departure_flight["outbound"]["departureDate"] = nice_date_format(
            departure_flight["outbound"]["departureDate"])
        arrival_date_depart = departure_flight["outbound"]["arrivalDate"] = nice_date_format(
            departure_flight["outbound"]["arrivalDate"])
        if result is None:

            continue
        else:
            depart1, return_flight, price = result

        departure_date_return = return_flight["outbound"]["departureDate"] = nice_date_format(
            return_flight["outbound"]["departureDate"])
        arrival_date_return = return_flight["outbound"]["arrivalDate"] = nice_date_format(
            return_flight["outbound"]["arrivalDate"])
        price_return = return_flight["outbound"]["price"]["value"]
        currency = return_flight["outbound"]["price"]["currencyCode"]

        if depart1 is None or return_flight is None:

            continue

        if price > float(budget):
            continue

        actual_dict[destination_name] = {}

        actual_dict[destination_name]["departures"] = depart1

        actual_dict[destination_name]["returns"] = return_flight
        actual_dict[destination_name]["price"] = round(price, 2)

        print("Flight")

        print(f"Depart {origin_name}, arrive {destination_name}, depart at time {
              departure_date_depart}, arrive at time {arrival_date_depart}")
        print(f"Depart {destination_name}, arrive {origin_name}, depart at time {
              departure_date_return}, arrive at time {arrival_date_return}")
        print(f"Total cost EUR{price}")
        total += 1

    sorted_dict = {k: v for k, v in sorted(
        actual_dict.items(), key=lambda x: x[1]["price"])}

    return sorted_dict


def nice_date_format(date):
    """
    Converts an ISO 8601 datetime string into a human-readable format.

    Parameters:
        date (str): A date string in ISO 8601 format, e.g., "2025-08-20T19:05:00".

    Returns:
        str: A formatted date string in the form "DD Month YYYY, HH:MM" (24-hour time),
             e.g., "20 August 2025, 19:05".
             If the input is invalid or cannot be parsed, returns None.
    """
    try:
        dt = datetime.fromisoformat(date)
        nice_format = dt.strftime("%d %B %Y, %H:%M")
        return nice_format
    except (ValueError, TypeError):
        return None


def get_ryanair_airports(csv_filepath_ryanair, csv_filepath_iata):
    """
    Reads two CSV files to return a list of Ryanair airports with full details.

    Parameters:
        csv_filepath_ryanair (str): Path to a CSV file containing Ryanair airport IATA codes.
        csv_filepath_iata (str): Path to a CSV file containing detailed airport info
                                 including iata_code, name, city, and country.

    Returns:
        list of dict: Each dictionary represents an airport with keys:
                      - 'code': IATA code
                      - 'name': Airport name
                      - 'city': City/municipality
                      - 'country': ISO country code
                      Only airports present in both CSV files are returned.
    """
    airports = {}
    with open(csv_filepath_iata, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            iata = row["iata_code"]
            name = row["name"]
            city = row["municipality"]
            country = row["iso_country"]
            airports[iata] = {
                "code": iata,
                "name": name,
                "city": city,
                "country": country
            }

    airports_of_interest = []
    with open(csv_filepath_ryanair, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["iata_code"] in airports:
                airports_of_interest.append(airports[row["iata_code"]])

    return airports_of_interest


def get_iata(origin_name, csv_filepath_iata):
    """
    Returns the IATA code for a given airport name from a CSV file.

    Parameters:
        origin_name (str): Name of the airport to look up.
        csv_filepath_iata (str): Path to a CSV file containing airport data 
                                 with at least 'name' and 'iata_code' columns.

    Returns:
        str or None: The IATA code if a match is found, otherwise None.
    """
    with open(csv_filepath_iata, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["name"] == origin_name:
                return row["iata_code"]
    return None

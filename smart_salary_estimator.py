def estimate_salary(title):
    title = title.lower()

    if "senior" in title:
        return "$140K-$190K"
    elif "sdet" in title:
        return "$130K-$180K"
    elif "qa" in title:
        return "$110K-$150K"
    else:
        return "$100K-$140K"

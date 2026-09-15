"""Screen logic checks for the nyscr / bidnet adapters. Run: python test_screens.py"""
import bidnet, nyscr

def bn(title, closing):
    return bidnet.screen({"title": title, "closing": closing})[0]

# awardable build survives; the four things that always waste a bid do not
assert bn("City Website Redesign Project", "12/01/2026") == "REVIEW"
assert bn("Artificial Intelligence Firearms Detection Software RFI", "12/01/2026") == "REJECT"
assert bn("SAP Staff Augmentation", "12/01/2026") == "REJECT"
assert bn("Justware Annual Maintenance and Support - Direct Award", "12/01/2026") == "REJECT"
assert bn("Subnet BAA", "12/01/2026") == "REJECT"
assert bn("Website Redesign", "") == "REJECT"                      # standing catalogue row
assert bn("Website Redesign", "01/01/2031") == "REJECT"            # open-ended vehicle
assert bn("Website Redesign", "08/27/2026") == "REJECT"            # too close to bid

def ny(title, due, cat=""):
    return nyscr.screen({"title": title, "due": due, "category": cat})[0]

assert ny("OCUE Modernization", "12/01/2026") == "REVIEW"
assert ny("NY-Sun Residential Incentive Program", "12/31/2030") == "REJECT"   # rolling enrolment
assert ny("Software Licence Renewal", "12/01/2026") == "REJECT"
assert ny("Snow Removal Services", "12/01/2026") == "WEAK"         # no build signal

print("ok")

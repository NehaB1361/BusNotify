/**
 * BusNotify - Bilingual Localization Module (English & Marathi)
 */

const I18N_DICTIONARY = {
  en: {
    brand_tagline: "Know your bus. Know your time.",
    home: "Home",
    search_bus: "Search Bus",
    live_status: "Live Status",
    favourites: "Favourites",
    emergency_updates: "Emergency Updates",
    notifications: "Notifications",
    profile: "Profile",
    where_going: "Where are you going?",
    search_placeholder: "Enter bus number, route, or stop...",
    source_placeholder: "Source stop (e.g. Pune Station)",
    dest_placeholder: "Destination (e.g. Hadapsar)",
    find_bus: "Find Bus",
    all: "All",
    on_time: "On Time",
    delayed: "Delayed",
    punctured: "Tyre Puncture",
    breakdown: "Breakdown",
    cancelled: "Cancelled",
    view_details: "View Details",
    current_stop: "Current Stop",
    next_stop: "Next Stop",
    available_seats: "Available Seats",
    expected_delay: "Historical Average Delay",
    stat_estimate_label: "Historical statistical estimate",
    stat_disclaimer: "This is a historical statistical estimate based on previous trip records and is not a guarantee.",
    alternative_buses: "Alternative Buses",
    recommended: "Recommended",
    replacement_status: "Replacement Status",
    dispatch_tracker: "Dispatch Tracker",
    start_trip: "Start Trip",
    end_trip: "End Trip",
    report_emergency: "Report Emergency",
    update_stop: "Update Stop",
    passenger_count: "Passenger Count",
    live_bus_monitor: "Live Bus Monitor",
    analytics: "Delay Analytics",
    depot_requests: "Emergency Depot Requests",
    assign_replacement: "Assign Replacement",
    dispatch: "Dispatch",
    mark_arrived: "Mark Arrived",
    record_transfer: "Record Transfer",
    resolve: "Resolve Request"
  },
  mr: {
    brand_tagline: "आपली बस जाणून घ्या. आपला वेळ वाचवा.",
    home: "मुख्यपृष्ठ",
    search_bus: "बस शोधा",
    live_status: "थेट स्थिती",
    favourites: "आवडते",
    emergency_updates: "आपत्कालीन सूचना",
    notifications: "सूचना",
    profile: "प्रोफाइल",
    where_going: "तुम्हाला कुठे जायचे आहे?",
    search_placeholder: "बस क्रमांक, मार्ग किंवा थांबा प्रविष्ट करा...",
    source_placeholder: "प्रारंभ थांबा (उदा. पुणे स्टेशन)",
    dest_placeholder: "गंतव्य थांबा (उदा. हडपसर)",
    find_bus: "बस शोधा",
    all: "सर्व",
    on_time: "वेळेवर",
    delayed: "विलंब",
    punctured: "टायर पंक्चर",
    breakdown: "बिघाड",
    cancelled: "रद्द",
    view_details: "तपशील पहा",
    current_stop: "सध्याचा थांबा",
    next_stop: "पुढील थांबा",
    available_seats: "उपलब्ध जागा",
    expected_delay: "ऐतिहासिक सरासरी विलंब",
    stat_estimate_label: "ऐतिहासिक सांख्यिकीय अंदाज",
    stat_disclaimer: "हा मागील ट्रिप नोंदींवर आधारित एक ऐतिहासिक सांख्यिकीय अंदाज आहे आणि हमी नाही.",
    alternative_buses: "पर्यायी बसेस",
    recommended: "शिफारस केलेले",
    replacement_status: "पर्यायी बस स्थिती",
    dispatch_tracker: "रवाना ट्रॅकर",
    start_trip: "प्रवास सुरू करा",
    end_trip: "प्रवास समाप्त करा",
    report_emergency: "आपत्कालीन नोंद करा",
    update_stop: "थांबा बदला",
    passenger_count: "प्रवासी संख्या",
    live_bus_monitor: "थेट बस मॉनिटर",
    analytics: "विलंब विश्लेषण",
    depot_requests: "डेपो आपत्कालीन विनंत्या",
    assign_replacement: "पर्यायी बस नियुक्त करा",
    dispatch: "रवाना करा",
    mark_arrived: "पोहोचले नोंदवा",
    record_transfer: "प्रवासी हस्तांतरण नोंदवा",
    resolve: "विनंती पूर्ण करा"
  }
};

let currentLang = localStorage.getItem('busnotify_lang') || 'en';

function setLanguage(lang) {
  if (lang !== 'en' && lang !== 'mr') lang = 'en';
  currentLang = lang;
  localStorage.setItem('busnotify_lang', lang);

  // Update DOM elements with data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (I18N_DICTIONARY[lang] && I18N_DICTIONARY[lang][key]) {
      if (el.tagName === 'INPUT' && el.getAttribute('placeholder')) {
        el.setAttribute('placeholder', I18N_DICTIONARY[lang][key]);
      } else {
        el.textContent = I18N_DICTIONARY[lang][key];
      }
    }
  });

  const btnText = document.getElementById('currentLangLabel');
  if (btnText) {
    btnText.textContent = lang === 'mr' ? 'मराठी' : 'English';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setLanguage(currentLang);
});

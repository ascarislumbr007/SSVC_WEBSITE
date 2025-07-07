# app.py

# --- Imports ---
import os
import json # Added for parsing Firebase credentials from environment variable
from dotenv import load_dotenv # For local development environment variables
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash

# Keep Firebase imports if other routes still use DB (like reviews, bookings, contacts)
import firebase_admin
from firebase_admin import credentials, firestore

from twilio.rest import Client

# Add this import for slugify
from slugify import slugify as py_slugify 


# --- Load environment variables from .env file (for local development ONLY) ---
# Vercel will ignore this and use its own environment variables.
load_dotenv()

# --- Flask App Initialization ---
app = Flask(__name__)

# --- IMPORTANT: Configure SECRET_KEY and DEBUG for production ---
# For security, these should be set as environment variables in Vercel.
# For local development, they will be loaded from your .env file (if you create one).
app.secret_key = os.environ.get('SECRET_KEY', 'a_very_strong_default_secret_key_for_local_dev_only')
app.debug = os.environ.get('FLASK_DEBUG') == '1' # Set FLASK_DEBUG=1 for debug mode locally, or don't set for production

# --- Firebase Initialization ---
db = None # Initialize db to None by default
FIREBASE_SERVICE_ACCOUNT_KEY = os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY')

if FIREBASE_SERVICE_ACCOUNT_KEY:
    try:
        # Firebase service account key is stored as a JSON string in an environment variable.
        # We need to parse it back into a dictionary for Firebase Admin SDK.
        cred_dict = json.loads(FIREBASE_SERVICE_ACCOUNT_KEY)
        cred = credentials.Certificate(cred_dict)
        
        # Initialize Firebase app only if it hasn't been initialized before
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase Initialized Successfully from environment variable.")
    except json.JSONDecodeError as e:
        print(f"Error parsing Firebase service account JSON from environment variable: {e}")
        print("Please ensure FIREBASE_SERVICE_ACCOUNT_KEY is a valid JSON string.")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
else:
    print("WARNING: FIREBASE_SERVICE_ACCOUNT_KEY environment variable not set. Firebase will not be initialized.")


# --- Twilio Configuration and Client Initialization ---
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

twilio_client = None
if all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("Twilio client initialized successfully from environment variables.")
    except Exception as e:
        print(f"Error initializing Twilio client: {e}")
else:
    print("WARNING: One or more Twilio environment variables are not set. SMS functionality will be disabled.")

# --- Register Custom Jinja2 Filters ---
@app.template_filter('slugify')
def jinja2_slugify(s):
    """
    Custom Jinja2 filter to slugify strings.
    Uses the python-slugify library.
    """
    return py_slugify(s)


# --- SMS Sending Function ---
def send_sms_notification(to_phone_number, message_body):
    """Sends an SMS notification using Twilio."""
    if not twilio_client:
        print("Twilio client is not initialized. Cannot send SMS.")
        return False
    if not to_phone_number or not message_body:
        print("Missing recipient phone number or message body for SMS.")
        return False

    try:
        message = twilio_client.messages.create(
            to=to_phone_number,
            from_=TWILIO_PHONE_NUMBER,
            body=message_body
        )
        print(f"SMS sent to {to_phone_number} successfully. SID: {message.sid}")
        return True
    except Exception as e:
        print(f"Error sending SMS to {to_phone_number}: {e}")
        return False

# --- Function to Retrieve Admin Phone Numbers from Firestore ---
def get_admin_phone_numbers():
    """Retrieves phone numbers of administrators from Firestore who want SMS notifications."""
    phone_numbers = []
    if not db:
        print("Firestore database client not initialized. Cannot fetch admin numbers.")
        return []
    try:
        admin_users_ref = db.collection('admin_users')
        docs = admin_users_ref.where('notification_preferences.sms_enabled', '==', True).stream()

        for doc in docs:
            phone = doc.get('phone_number')
            if phone:
                phone_numbers.append(phone)
    except Exception as e:
        print(f"Error retrieving admin phone numbers from Firestore: {e}")
    return phone_numbers


# --- Routes ---
@app.route('/')
@app.route('/home')
def home():
    reviews_list = []
    if db: # This part still uses Firebase for reviews
        try:
            # Fetch only approved reviews
            docs = db.collection('reviews').where('approved', '==', True).stream()
            for doc in docs:
                review_data = doc.to_dict()
                reviews_list.append(review_data)
            print(f"DEBUG: Fetched {len(reviews_list)} reviews from Firestore.")
        except Exception as e:
            print(f"Error fetching reviews from Firestore: {e}")
            # Fallback to dummy data if Firestore fails
            reviews_list = [
                {"quote": "The food was absolutely amazing! Our guests couldn't stop talking about it. Highly recommended!", "author": "Jahnavi"},
                {"quote": "Professional service and delicious vegetarian options. Sri Sai Venkateswara Caterers made our event special.", "author": "Kishore"},
            ]
    else:
        print("DEBUG: Firestore not available. Using dummy reviews.")
        reviews_list = [
            {"quote": "The food was absolutely amazing! Our guests couldn't stop talking about it. Highly recommended!", "author": "Jahnavi"},
            {"quote": "Professional service and delicious vegetarian options. Sri Sai Venkateswara Caterers made our event special.", "author": "Kishore"},
        ]

    return render_template('index.html',
                           title='Home - Sri Sai Venkateswara Caterers',
                           testimonials=reviews_list,
                           num_testimonials=len(reviews_list)
                          )

@app.route('/menu')
def menu_page():
    # --- STATIC MENU DATA for image-based display ---
    # Using the provided menu images directly
    menu_sections = [
        {'id': 'section1', 'name': 'Welcome Drinks & Starters', 'image': url_for('static', filename='images/menu1.jpg'), 'description': 'A delightful array of welcome drinks and appetizers.'},
        {'id': 'section2', 'name': 'Breakfast, Snacks & Soups', 'image': url_for('static', filename='images/menu2.jpg'), 'description': 'Hearty breakfast, quick bites, and comforting soups.'},
        {'id': 'section3', 'name': 'Main Courses & Sides', 'image': url_for('static', filename='images/menu3.jpg'), 'description': 'North & South Indian curries, dals, rices, and fries.'},
        {'id': 'section4', 'name': 'Sweets, Ice Creams & Special Counters', 'image': url_for('static', filename='images/menu4.jpg'), 'description': 'Indulgent desserts, refreshing ice creams, and live counters.'}
    ]

    terms_and_conditions = [
        "Transportation Included",
        "The total package includes disposables, cutlery, serving boys.",
        "Live Preparation Will Be Charged Extra Depending On Items (For Example: Rumali Roti, Puri, Butter Naan, Mirchi Bajji, Bobbatu, Boorelu, etc.)",
        "We deliberately provide extra food at 10%. In case it exceeds the allocated amount, an additional charge per person will apply.",
        "Orders will be confirmed after providing the event date, number of guests, meal preference (lunch/breakfast/dinner).",
        "The contact person's primary number, along with an alternative number, should be provided in advance.",
        "The host is responsible for arranging tables, tablecloths, dustbins, cloth and frills etc.",
        "There is no additional cost for buffet service. However, for Aritaka Bhojanam, additional charges will apply.",
        "At least 25% advance payment is required out of the total agreed amount at the time of confirmation. The remaining balance can be paid after the event.",
        "The above package and some terms and conditions apply for a minimum guest size of 100 (not less than 100).",
        "Guest Size Below 100 will have a package price – No Bargain",
        
    ]

    return render_template('menu.html',
                           title='Our Menu - Sri Sai Venkateswara Caterers',
                           menu_sections=menu_sections, # Changed variable name to menu_sections
                           terms_and_conditions=terms_and_conditions
                          )

# --- Other existing routes ---
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    print(f"DEBUG: Contact route accessed. Method: {request.method}")
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message = request.form.get('message')
        subject = request.form.get('subject') # Added subject

        print(f"DEBUG: Contact form data - Name: {name}, Email: {email}, Phone: {phone}, Subject: {subject}, Message: {message}")

        if not name or not email or not message:
            print("ERROR: Name, email, or message missing for contact form.")
            return jsonify({'success': False, 'message': 'Please fill in all required fields.'}), 400

        try:
            if db:
                doc_ref = db.collection('contacts').add({
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'subject': subject, # Save subject
                    'message': message,
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
                print(f"DEBUG: Contact message saved with ID: {doc_ref[1].id}")

            admin_numbers = get_admin_phone_numbers()
            if admin_numbers:
                # Updated SMS body for contact form
                sms_body = (f"New Contact Form Submission:\n"
                            f"Name: {name}\n"
                            f"Email: {email}\n"
                            f"Phone: {phone}\n"
                            f"Subject: {subject if subject else 'N/A'}\n"
                            f"Message: {message[:100]}...") # Truncate message for SMS
                print(f"DEBUG: Sending contact SMS: {sms_body}")
                for admin_phone in admin_numbers:
                    send_sms_notification(admin_phone, sms_body)
            else:
                print("DEBUG: No admin numbers found for SMS notification (contact form).")
            
            return jsonify({'success': True, 'message': 'Your message has been sent successfully!'}), 200
        except Exception as e:
            print(f"EXCEPTION: Error handling contact form: {e}")
            return jsonify({'success': False, 'message': 'An error occurred while sending your message. Please try again later.'}), 500
    
    return render_template('contact.html', title='Contact Us')


@app.route('/book', methods=['GET', 'POST'])
def book():
    print(f"DEBUG: Book route accessed. Method: {request.method}")
    if request.method == 'POST':
        event_type = request.form.get('eventType')
        event_date = request.form.get('eventDate')
        num_guests = request.form.get('numGuests')
        customer_name = request.form.get('customerName')
        customer_email = request.form.get('customerEmail')
        customer_phone = request.form.get('customerPhone')
        special_requests = request.form.get('specialRequests')

        print(f"DEBUG: Booking form data - Type: {event_type}, Date: {event_date}, Guests: {num_guests}, Name: {customer_name}, Phone: {customer_phone}")

        if not all([event_type, event_date, num_guests, customer_name, customer_email, customer_phone]):
            print("ERROR: Missing required booking fields.")
            return jsonify({'success': False, 'message': 'Please fill in all required fields.'}), 400

        try:
            if db:
                doc_ref = db.collection('bookings').add({
                    'event_type': event_type,
                    'event_date': event_date,
                    'num_guests': num_guests,
                    'customer_name': customer_name,
                    'customer_email': customer_email,
                    'customer_phone': customer_phone,
                    'special_requests': special_requests,
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
                print(f"DEBUG: Booking saved with ID: {doc_ref[1].id}")

            admin_numbers = get_admin_phone_numbers()
            if admin_numbers:
                # UPDATED SMS BODY FOR BOOKING FORM TO MATCH PREVIOUS FORMAT
                sms_body = (f"Customer: {customer_name}\n"
                            f"Contact: {customer_phone} | {customer_email}\n"
                            f"Event: {event_type} for {num_guests} guests on {event_date}.\n"
                            f"Message: {special_requests if special_requests else 'N/A'}")
                print(f"DEBUG: Sending booking SMS: {sms_body}")
                for admin_phone in admin_numbers:
                    send_sms_notification(admin_phone, sms_body)
            else:
                print("DEBUG: No admin numbers found for SMS notification (booking form).")

            return jsonify({'success': True, 'message': 'Your booking request has been sent successfully! We will contact you soon.'}), 200
        except Exception as e:
            print(f"EXCEPTION: Error handling booking form: {e}")
            return jsonify({'success': False, 'message': 'An error occurred while processing your booking. Please try again later.'}), 500
            
    return render_template('book.html', title='Book Our Services')

# --- Add the about route (endpoint name 'about') ---
@app.route('/about')
def about():
    return render_template('about.html', title='About Us - Sri Sai Venkateswara Caterers')

# --- Add the submit_review route (endpoint name 'submit_review') ---
   # app.py (excerpt - only showing the relevant part)

   # ... (previous code) ...

@app.route('/submit_review', methods=['GET', 'POST'])
def submit_review():
       print(f"DEBUG: submit_review route accessed. Method: {request.method}")
       if request.method == 'POST':
           reviewer_name = request.form.get('author')
           review_quote = request.form.get('quote')
           rating = request.form.get('rating')

           print(f"DEBUG: Received data - Name: {reviewer_name}, Quote: {review_quote}, Rating: {rating}")

           if not reviewer_name or not review_quote:
               print("ERROR: Name or review quote missing.")
               return jsonify({'success': False, 'message': 'Your name and review are required.'}), 400

           try:
               if db: # Ensure db is initialized from Firebase setup
                   # Convert rating to int, handle empty string if optional
                   try:
                       rating_value = int(rating) if rating and rating.strip() else None
                   except ValueError:
                       print(f"WARNING: Invalid rating value received: {rating}. Setting to None.")
                       rating_value = None

                   doc_ref = db.collection('reviews').add({
                       'author': reviewer_name,
                       'quote': review_quote,
                       'rating': rating_value,
                       'approved': False, # Reviews should probably be approved by an admin before showing on homepage
                       'timestamp': firestore.SERVER_TIMESTAMP
                   })
                   print(f"DEBUG: Review saved to Firestore with ID: {doc_ref[1].id}")
                   return jsonify({'success': True, 'message': 'Thank you for your review!'}), 200
               else:
                   # This means Firebase did not initialize.
                   print("ERROR: Firestore database client not initialized. Cannot save review.")
                   return jsonify({'success': False, 'message': 'Database not available. Cannot save review. Please contact support.'}), 500
           except Exception as e:
               # --- IMPORTANT CHANGE HERE ---
               import traceback
               print(f"EXCEPTION: Error saving review to Firestore: {e}")
               print("TRACEBACK:")
               traceback.print_exc() # This will print the full traceback to the console/logs
               # --- END IMPORTANT CHANGE ---
               return jsonify({'success': False, 'message': f'An unexpected error occurred: {str(e)}'}), 500
       
       # For GET request, just render the form
       return render_template('submit_review.html', title='Submit Your Review - Sri Sai Venkateswara Caterers')
   
   

@app.route('/privacy-policy')
def privacy_policy_page():
    """Renders the privacy policy page."""
    return render_template('privacy_policy.html', active_page='privacy_policy')

@app.route('/terms-conditions')
def terms_and_conditions_page():
    """Renders the terms and conditions page."""
    return render_template('terms_and_conditions.html', active_page='terms_and_conditions')


# --- Run the Flask App ---
if __name__ == '__main__':
    # Use the debug setting from environment variable for local run
    app.run(debug=app.debug)


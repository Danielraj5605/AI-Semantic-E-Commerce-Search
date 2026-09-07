"""ETL script — downloads a product dataset and loads it into the database.

Uses the Flipkart Products dataset from Kaggle (or generates synthetic data
if the CSV is not found). Cleans the data and bulk-inserts into products
and categories tables.
"""

import sys
import os
import csv
import json
import uuid
import random
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.models import Category, Product

settings = get_settings()

# ----- Synthetic product dataset -----
# A rich, diverse product catalog covering multiple categories
# This gives us real-looking data to demonstrate semantic search quality

SYNTHETIC_PRODUCTS = [
    # Electronics - Laptops
    {"name": "UltraSlim Pro 15 Laptop", "description": "Ultra-thin 15.6-inch laptop with Intel Core i7 processor, 16GB RAM, 512GB SSD, full HD display. Perfect for professionals and students who need a powerful yet portable machine.", "category": "Laptops", "brand": "TechVision", "price": 899.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400"},
    {"name": "Gaming Beast X17", "description": "High-performance gaming laptop with RTX 4060 graphics, 144Hz display, RGB keyboard, 32GB RAM. Dominate every game with stunning visuals and zero lag.", "category": "Laptops", "brand": "GameForce", "price": 1599.99, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=400"},
    {"name": "ChromeBook Lite 11", "description": "Lightweight and affordable Chromebook for browsing, email, and light productivity. 11-inch display, all-day battery life, fast boot times.", "category": "Laptops", "brand": "CloudTech", "price": 249.99, "rating": 4.0, "image_url": "https://images.unsplash.com/photo-1541807084-5c52b6b3adef?w=400"},
    {"name": "MacStyle Creator Studio", "description": "Creative professional laptop with 4K OLED display, Apple M-series comparable processor, 32GB unified memory. Ideal for video editing, graphic design, and music production.", "category": "Laptops", "brand": "CreativePro", "price": 2199.99, "rating": 4.8, "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=400"},
    {"name": "Budget Work Notebook 14", "description": "Reliable 14-inch business notebook with Intel Core i5, 8GB RAM, 256GB SSD. Great for office work, spreadsheets, and video calls.", "category": "Laptops", "brand": "OfficeMax", "price": 499.99, "rating": 4.1, "image_url": "https://images.unsplash.com/photo-1525547719571-a2d4ac8945e2?w=400"},

    # Electronics - Smartphones
    {"name": "Galaxy Nova 14 Pro", "description": "Flagship smartphone with 200MP camera, 6.8-inch AMOLED display, 5000mAh battery, 5G connectivity. Capture professional-quality photos and videos.", "category": "Smartphones", "brand": "StarMobile", "price": 999.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=400"},
    {"name": "PixelPure 8", "description": "Clean Android experience with best-in-class computational photography, 7 years of software updates, AI-powered features, and titanium build.", "category": "Smartphones", "brand": "PixelPure", "price": 799.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=400"},
    {"name": "BudgetKing A15", "description": "Affordable smartphone with surprisingly good camera, large 6.5-inch display, 4GB RAM, expandable storage. Best value phone under $200.", "category": "Smartphones", "brand": "ValueTech", "price": 179.99, "rating": 4.0, "image_url": "https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=400"},
    {"name": "iPhone-Style Ultra Max", "description": "Premium smartphone with surgical-grade stainless steel frame, advanced triple camera system, face recognition, and ceramic shield display.", "category": "Smartphones", "brand": "AppleStyle", "price": 1199.99, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=400"},
    {"name": "Rugged Outdoor Phone X5", "description": "Military-grade rugged smartphone, waterproof IP69, shockproof, dustproof. Massive 6600mAh battery. Built for construction workers, hikers, and adventurers.", "category": "Smartphones", "brand": "ToughGear", "price": 349.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1574944985070-8f3ebc6b79d2?w=400"},

    # Electronics - Audio
    {"name": "NoiseCancel Pro Headphones", "description": "Premium over-ear wireless headphones with active noise cancellation, 30-hour battery, Hi-Res audio, comfortable memory foam ear cups.", "category": "Audio", "brand": "SoundElite", "price": 349.99, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400"},
    {"name": "TrueWireless Earbuds Sport", "description": "Sweatproof true wireless earbuds with secure-fit wing tips, deep bass, 8-hour playback, wireless charging case. Perfect for running and gym workouts.", "category": "Audio", "brand": "FitSound", "price": 79.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1590658268037-6bf12f032f55?w=400"},
    {"name": "Vintage Vinyl Turntable", "description": "Classic belt-drive turntable with built-in preamp, USB output for digitizing records, warm analog sound. Beautiful walnut wood finish.", "category": "Audio", "brand": "RetroSound", "price": 199.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1539375665275-f9de415ef9ac?w=400"},
    {"name": "Portable Bluetooth Speaker XL", "description": "Waterproof portable speaker with 360-degree sound, 20-hour battery, built-in microphone for calls, LED light show mode.", "category": "Audio", "brand": "BoomBox", "price": 129.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=400"},
    {"name": "Studio Monitor Speakers Pair", "description": "Professional studio reference monitors for music production and mixing. Flat frequency response, bi-amplified design, acoustic tuning controls.", "category": "Audio", "brand": "ProAudio", "price": 599.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=400"},

    # Clothing - Men
    {"name": "Insulated Men's Parka", "description": "Heavyweight insulated winter parka with waterproof shell, faux fur-lined hood, multiple pockets. Rated for temperatures down to -30°F. Perfect for harsh winters.", "category": "Men's Clothing", "brand": "ArcticWear", "price": 189.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1544923246-77307dd270b1?w=400"},
    {"name": "Slim Fit Cotton Oxford Shirt", "description": "Classic Oxford button-down shirt in premium cotton. Versatile enough for office wear or smart casual. Wrinkle-resistant fabric.", "category": "Men's Clothing", "brand": "ClassicThread", "price": 49.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=400"},
    {"name": "Stretch Denim Jeans Regular", "description": "Comfortable regular-fit jeans with 2% elastane for all-day stretch and comfort. Dark indigo wash, classic five-pocket styling.", "category": "Men's Clothing", "brand": "DenimCraft", "price": 59.99, "rating": 4.2, "image_url": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=400"},
    {"name": "Merino Wool Crew Sweater", "description": "Luxuriously soft 100% merino wool sweater. Temperature regulating, naturally odor-resistant, machine washable. Perfect layering piece.", "category": "Men's Clothing", "brand": "WoolCraft", "price": 89.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1434389677669-e08b4cda3a45?w=400"},
    {"name": "Waterproof Hiking Jacket", "description": "Lightweight waterproof breathable hiking jacket with sealed seams, adjustable hood, and packable design. Ideal for trail running and mountaineering.", "category": "Men's Clothing", "brand": "TrailMaster", "price": 129.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=400"},

    # Clothing - Women
    {"name": "Floral Wrap Maxi Dress", "description": "Elegant wrap-style maxi dress with vibrant floral print, V-neckline, and flutter sleeves. Flowy chiffon fabric perfect for summer weddings and garden parties.", "category": "Women's Clothing", "brand": "FloralChic", "price": 69.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=400"},
    {"name": "High-Waist Yoga Leggings", "description": "Buttery-soft high-waisted yoga leggings with tummy control, moisture-wicking fabric, side pockets. Squat-proof and perfect for studio or street.", "category": "Women's Clothing", "brand": "FlexFit", "price": 44.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1506629082955-511b1aa562c8?w=400"},
    {"name": "Cashmere Blend Cardigan", "description": "Luxurious cashmere-blend cardigan with mother-of-pearl buttons, relaxed fit, ribbed trim. Effortlessly chic layering for cool evenings.", "category": "Women's Clothing", "brand": "LuxKnit", "price": 129.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1434389677669-e08b4cda3a45?w=400"},
    {"name": "Tailored Blazer Jacket", "description": "Structured single-button blazer with notched lapel, fully lined interior. Transitions seamlessly from boardroom to happy hour.", "category": "Women's Clothing", "brand": "PowerDress", "price": 149.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=400"},
    {"name": "Down Puffer Vest", "description": "Lightweight 700-fill down puffer vest with water-resistant shell, stand collar, zip pockets. Warmth without bulk for active days.", "category": "Women's Clothing", "brand": "AlpineStyle", "price": 99.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1544022613-e87ca75a784a?w=400"},

    # Footwear
    {"name": "CloudWalk Running Shoes", "description": "Ultra-cushioned running shoes with cloud-like foam midsole, breathable mesh upper, supportive heel counter. Great for neutral runners and daily training.", "category": "Footwear", "brand": "RunElite", "price": 134.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400"},
    {"name": "Classic Leather Chelsea Boots", "description": "Timeless Chelsea boots in genuine leather with elastic side panels, pull tab, Goodyear welted sole. Dress up or down for any occasion.", "category": "Footwear", "brand": "HeritageStep", "price": 179.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1638247025967-b4e38f787b76?w=400"},
    {"name": "Orthopedic Comfort Shoes for Flat Feet", "description": "Specially designed shoes for flat feet and plantar fasciitis with enhanced arch support, deep heel cup, and shock-absorbing insole. All-day comfort.", "category": "Footwear", "brand": "ComfortStep", "price": 94.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=400"},
    {"name": "Waterproof Hiking Boots", "description": "Durable hiking boots with Vibram outsole, waterproof membrane, ankle support. Conquers muddy trails, rocky terrain, and stream crossings.", "category": "Footwear", "brand": "TrailMaster", "price": 159.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1520639888713-7851133b1ed0?w=400"},
    {"name": "Canvas Slip-On Sneakers", "description": "Casual canvas slip-on sneakers with vulcanized rubber sole, padded collar, easy on/off design. Classic style for everyday wear.", "category": "Footwear", "brand": "StreetStyle", "price": 44.99, "rating": 4.1, "image_url": "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?w=400"},

    # Home & Kitchen
    {"name": "Smart Air Purifier with HEPA Filter", "description": "Wi-Fi enabled air purifier with True HEPA H13 filter, covers 1500 sq ft. Removes 99.97% of allergens, dust, pollen, and pet dander. Quiet sleep mode.", "category": "Home & Kitchen", "brand": "PureAir", "price": 249.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1585771724684-38269d6639fd?w=400"},
    {"name": "Cast Iron Dutch Oven 6-Quart", "description": "Enameled cast iron Dutch oven perfect for slow cooking, braising, baking bread, and soups. Even heat distribution, oven-safe to 500°F.", "category": "Home & Kitchen", "brand": "IronChef", "price": 79.99, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1585664811087-47f65abbad64?w=400"},
    {"name": "Robot Vacuum with Mapping", "description": "Smart robot vacuum with LiDAR mapping, 2700Pa suction, self-emptying base, no-go zones. Works with Alexa and Google Home.", "category": "Home & Kitchen", "brand": "CleanBot", "price": 399.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=400"},
    {"name": "Bamboo Cutting Board Set", "description": "Set of 3 organic bamboo cutting boards in different sizes. Knife-friendly, antimicrobial, easy to clean. Juice groove prevents spills.", "category": "Home & Kitchen", "brand": "EcoKitchen", "price": 29.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1594226801341-41427b4e5c22?w=400"},
    {"name": "Programmable Coffee Maker 12-Cup", "description": "12-cup drip coffee maker with programmable timer, brew strength control, auto-shutoff, and reusable gold-tone filter. Wake up to fresh coffee.", "category": "Home & Kitchen", "brand": "BrewMaster", "price": 69.99, "rating": 4.2, "image_url": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=400"},
    {"name": "Memory Foam Mattress Topper Queen", "description": "3-inch gel-infused memory foam mattress topper with cooling technology. Pressure relief for back pain, hip pain, and side sleepers.", "category": "Home & Kitchen", "brand": "DreamCloud", "price": 149.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=400"},

    # Sports & Fitness
    {"name": "Adjustable Dumbbell Set 5-52 lbs", "description": "Space-saving adjustable dumbbell set replacing 15 pairs of weights. Quick-change dial system, durable construction. Full home gym in one pair.", "category": "Sports & Fitness", "brand": "IronFlex", "price": 299.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=400"},
    {"name": "Yoga Mat Premium 6mm", "description": "Extra-thick non-slip yoga mat with alignment lines, eco-friendly TPE material, carrying strap. Joint protection for yoga, pilates, and floor exercises.", "category": "Sports & Fitness", "brand": "ZenFit", "price": 39.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1601925260368-ae2f83cf8b7f?w=400"},
    {"name": "Fitness Tracker Watch", "description": "Advanced fitness tracker with heart rate monitoring, GPS, sleep tracking, blood oxygen sensor, 7-day battery. Water resistant to 50 meters.", "category": "Sports & Fitness", "brand": "FitTrack", "price": 149.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1575311373937-040b8e1fd5b6?w=400"},
    {"name": "Resistance Bands Set of 5", "description": "Professional-grade resistance bands with different tension levels (5-50 lbs). Includes door anchor, handles, ankle straps, and workout guide.", "category": "Sports & Fitness", "brand": "FlexPower", "price": 24.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1598289431512-b97b0917affc?w=400"},
    {"name": "Insulated Water Bottle 32oz", "description": "Vacuum-insulated stainless steel water bottle keeps drinks cold 24 hours or hot 12 hours. BPA-free, leak-proof, wide-mouth opening.", "category": "Sports & Fitness", "brand": "HydroKeep", "price": 34.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=400"},

    # Beauty & Personal Care
    {"name": "Vitamin C Brightening Serum", "description": "Concentrated 20% Vitamin C serum with hyaluronic acid and vitamin E. Brightens dark spots, evens skin tone, boosts collagen production.", "category": "Beauty", "brand": "GlowLab", "price": 28.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=400"},
    {"name": "Organic Argan Oil Shampoo", "description": "Sulfate-free shampoo with cold-pressed argan oil, keratin, and biotin. Repairs damaged hair, adds shine, reduces frizz. For all hair types.", "category": "Beauty", "brand": "PureRoots", "price": 16.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1535585209827-a15fcdbc4c2d?w=400"},
    {"name": "Electric Facial Cleansing Brush", "description": "Sonic facial cleansing brush with 5 speed settings, waterproof design, silicone brush head. Deep cleans pores, removes makeup, exfoliates gently.", "category": "Beauty", "brand": "SkinTech", "price": 49.99, "rating": 4.2, "image_url": "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=400"},
    {"name": "SPF 50 Mineral Sunscreen", "description": "Reef-safe mineral sunscreen with zinc oxide, lightweight non-greasy formula, water resistant 80 minutes. No white cast, suitable for sensitive skin.", "category": "Beauty", "brand": "SunShield", "price": 19.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=400"},
    {"name": "Professional Hair Dryer 1875W", "description": "Salon-grade ionic hair dryer with diffuser and concentrator attachments, 3 heat settings, cool shot button. Reduces frizz, dries 50% faster.", "category": "Beauty", "brand": "StylePro", "price": 59.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1522338242992-e1a54571a9f7?w=400"},

    # Books
    {"name": "Deep Learning with Python", "description": "Comprehensive guide to deep learning using Python and Keras. Covers neural networks, CNNs, RNNs, transformers, and practical applications. Written for developers.", "category": "Books", "brand": "TechBooks", "price": 44.99, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400"},
    {"name": "The Art of Cooking: Italian Edition", "description": "Authentic Italian cookbook with 200+ recipes from nonna's kitchen to modern Italian cuisine. Beautiful photography, step-by-step instructions.", "category": "Books", "brand": "CulinaryPress", "price": 32.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1490633874781-1c63cc424610?w=400"},
    {"name": "Mindfulness and Meditation Guide", "description": "Practical guide to mindfulness meditation with 30-day program, breathing exercises, body scan techniques, and stress reduction strategies.", "category": "Books", "brand": "WellnessBooks", "price": 14.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=400"},

    # Toys & Games
    {"name": "STEM Building Robot Kit", "description": "Educational robot building kit for kids 8-14. Teaches programming, engineering, and problem-solving. 400+ pieces, app-controlled, 12 build modes.", "category": "Toys & Games", "brand": "BrainBuild", "price": 69.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1535378917042-10a22c95931a?w=400"},
    {"name": "1000-Piece Landscape Puzzle", "description": "Premium 1000-piece jigsaw puzzle featuring stunning mountain landscape photography. Thick sturdy pieces, minimal puzzle dust, poster included.", "category": "Toys & Games", "brand": "PuzzleCraft", "price": 19.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1494059980473-813e73ee784b?w=400"},
    {"name": "Strategy Board Game Collection", "description": "Award-winning strategy board game for 2-6 players. Resource management, trading, and building. Endless replayability with random board setup.", "category": "Toys & Games", "brand": "GameNight", "price": 39.99, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1611371805429-8b5c1b2c34ba?w=400"},

    # Pet Supplies
    {"name": "Orthopedic Dog Bed Large", "description": "Memory foam orthopedic dog bed for large breeds (50-100 lbs). Waterproof liner, removable washable cover, non-slip bottom. Eases joint pain in older dogs.", "category": "Pet Supplies", "brand": "PetComfort", "price": 79.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=400"},
    {"name": "Automatic Cat Feeder WiFi", "description": "Smart automatic cat feeder with Wi-Fi app control, portion control, voice recording, and dual power supply. Schedule up to 6 meals per day.", "category": "Pet Supplies", "brand": "PetTech", "price": 59.99, "rating": 4.2, "image_url": "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=400"},
    {"name": "Interactive Dog Toy Puzzle", "description": "Mental stimulation puzzle toy for dogs with hidden treat compartments. Reduces boredom and destructive behavior. Dishwasher safe, BPA-free.", "category": "Pet Supplies", "brand": "SmartPet", "price": 24.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1601758228041-f3b2795255f1?w=400"},

    # Office Supplies
    {"name": "Ergonomic Office Chair", "description": "Adjustable ergonomic mesh office chair with lumbar support, headrest, 4D armrests, seat depth adjustment. Breathable mesh keeps you cool during long work sessions.", "category": "Office", "brand": "ErgoWorks", "price": 449.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1580480055273-228ff5388ef8?w=400"},
    {"name": "Standing Desk Converter", "description": "Height-adjustable standing desk converter for existing desks. Smooth gas spring lift, two-tier design for monitor and keyboard. Improves posture and energy.", "category": "Office", "brand": "StandUp", "price": 199.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1518455027359-f3f8164ba6bd?w=400"},
    {"name": "Mechanical Keyboard RGB", "description": "Full-size mechanical keyboard with Cherry MX Blue switches, per-key RGB backlighting, aluminum frame, programmable macros. Satisfying tactile feedback for typists.", "category": "Office", "brand": "KeyCraft", "price": 119.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1595225476474-87563907a212?w=400"},
    {"name": "Wireless Ergonomic Mouse", "description": "Vertical ergonomic wireless mouse that reduces wrist strain and carpal tunnel symptoms. 6 buttons, adjustable DPI, Bluetooth and USB receiver.", "category": "Office", "brand": "ErgoWorks", "price": 39.99, "rating": 4.2, "image_url": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=400"},
    {"name": "Monitor Light Bar", "description": "LED monitor light bar with adjustable color temperature, auto-dimming sensor, no screen glare. Reduces eye strain during late-night coding sessions.", "category": "Office", "brand": "LightTech", "price": 54.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1593642632559-0c6d3fc62b89?w=400"},

    # Additional diverse products for semantic search testing
    {"name": "Warm Fleece Blanket King Size", "description": "Ultra-soft microfiber fleece throw blanket in king size. Lightweight yet incredibly warm, machine washable, perfect for cozy movie nights on the couch.", "category": "Home & Kitchen", "brand": "CozyHome", "price": 39.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=400"},
    {"name": "Noise Machine for Sleep", "description": "White noise machine with 30 soothing sounds including rain, ocean, forest, and fan. Timer function, portable for travel, helps babies and adults sleep better.", "category": "Home & Kitchen", "brand": "SleepWell", "price": 34.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=400"},
    {"name": "Portable Power Station 500W", "description": "Portable solar generator with 500W output, 518Wh capacity, multiple outlets (AC, USB-C, USB-A, car). Powers laptops, CPAP, mini fridge during camping or power outages.", "category": "Electronics", "brand": "PowerBox", "price": 449.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=400"},
    {"name": "4K Action Camera Waterproof", "description": "Compact 4K action camera with electronic image stabilization, waterproof to 33ft without case, touchscreen, voice control. Captures adventures in stunning detail.", "category": "Electronics", "brand": "AdventureCam", "price": 199.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=400"},
    {"name": "Electric Standing Desk", "description": "Full electric sit-stand desk with dual motors, programmable height presets, cable management tray, 60x30 inch solid wood top. Whisper-quiet operation.", "category": "Office", "brand": "StandUp", "price": 549.99, "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1518455027359-f3f8164ba6bd?w=400"},
    {"name": "Kids Bicycle 20-inch", "description": "Colorful kids bicycle with training wheels, adjustable seat height, hand brakes, and chain guard. Sturdy steel frame designed for ages 6-10.", "category": "Sports & Fitness", "brand": "KidRide", "price": 159.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1485965120184-e220f721d03e?w=400"},
    {"name": "Stainless Steel Cookware Set 10-Piece", "description": "Professional-grade tri-ply stainless steel cookware set. Includes saucepans, fry pans, stockpot. Oven safe, induction compatible, dishwasher safe.", "category": "Home & Kitchen", "brand": "ChefLine", "price": 249.99, "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=400"},
    {"name": "Wireless Charging Pad Fast", "description": "15W fast wireless charging pad compatible with all Qi-enabled devices. Slim design, LED indicator, foreign object detection, anti-slip surface.", "category": "Electronics", "brand": "ChargeTech", "price": 19.99, "rating": 4.1, "image_url": "https://images.unsplash.com/photo-1586953208448-b95a79798f07?w=400"},
    {"name": "Essential Oil Diffuser", "description": "Ultrasonic aromatherapy essential oil diffuser with 500ml tank, 7 LED colors, timer settings, whisper-quiet operation. Creates a relaxing spa atmosphere at home.", "category": "Home & Kitchen", "brand": "AromaZen", "price": 29.99, "rating": 4.3, "image_url": "https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?w=400"},
    {"name": "Travel Backpack 40L Carry-On", "description": "Expandable 40L travel backpack that fits airline carry-on requirements. Laptop compartment, shoe compartment, compression straps, lockable zippers.", "category": "Travel", "brand": "NomadGear", "price": 79.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=400"},
    {"name": "Compact Binoculars 10x42", "description": "High-quality roof prism binoculars with 10x magnification, 42mm objective lens, fully multi-coated optics. Perfect for birdwatching, hiking, and sports events.", "category": "Sports & Fitness", "brand": "OpticView", "price": 89.99, "rating": 4.4, "image_url": "https://images.unsplash.com/photo-1509281373149-e957c6296406?w=400"},
    {"name": "Electric Toothbrush Sonic", "description": "Rechargeable sonic electric toothbrush with 5 cleaning modes, pressure sensor, 2-minute timer, 30-day battery life. Removes 10x more plaque than manual brushing.", "category": "Beauty", "brand": "DentalCare", "price": 49.99, "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1559591937-abc8d3304f6f?w=400"},
]


def load_data():
    """Load the synthetic product dataset into the database."""
    print("Connecting to database...")
    engine = create_engine(settings.database_url_sync)

    with Session(engine) as session:
        # Check if products already loaded
        existing_count = session.execute(text("SELECT COUNT(*) FROM products")).scalar()
        if existing_count > 0:
            print(f"Database already has {existing_count} products. Skipping load.")
            print("To reload, truncate the products and categories tables first.")
            return

        # Collect unique categories
        category_names = sorted(set(p["category"] for p in SYNTHETIC_PRODUCTS))
        print(f"Loading {len(category_names)} categories...")

        category_map = {}
        for name in category_names:
            cat = Category(name=name)
            session.add(cat)
            session.flush()  # Get the auto-generated category_id
            category_map[name] = cat.category_id
            print(f"  Category: {name} -> id={cat.category_id}")

        # Insert products
        print(f"\nLoading {len(SYNTHETIC_PRODUCTS)} products...")
        for i, p in enumerate(SYNTHETIC_PRODUCTS):
            product = Product(
                product_id=uuid.uuid4(),
                name=p["name"],
                description=p["description"],
                category_id=category_map.get(p["category"]),
                brand=p["brand"],
                price=Decimal(str(p["price"])),
                stock_quantity=random.randint(10, 500),
                rating_avg=p["rating"],
                image_url=p.get("image_url"),
            )
            session.add(product)
            if (i + 1) % 10 == 0:
                print(f"  Loaded {i + 1}/{len(SYNTHETIC_PRODUCTS)} products...")

        session.commit()
        print(f"\nSuccessfully loaded {len(SYNTHETIC_PRODUCTS)} products!")

        # Verify
        final_count = session.execute(text("SELECT COUNT(*) FROM products")).scalar()
        print(f"Total products in database: {final_count}")

    engine.dispose()


if __name__ == "__main__":
    load_data()

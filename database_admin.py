import argparse
import bcrypt
import json
from pymongo import MongoClient

def create_or_update_user(email, password):
    with open('config.json') as config_file:
        config = json.load(config_file)

    client = MongoClient(config['MONGO_URI'])
    db = client['brownotate-db']
    users_collection = db['users']

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        # Cherche un utilisateur avec le même email
        existing_user = users_collection.find_one({'email': email})

        if existing_user:
            # Si l'utilisateur existe, mettre à jour le mot de passe
            result = users_collection.update_one(
                {'email': email},
                {'$set': {'password_hash': password_hash}}
            )
            if result.matched_count > 0:
                print(f"Password updated for user with email: {email}")
            else:
                print(f"User with email {email} not found for update.")
        else:
            # Si l'utilisateur n'existe pas, créer un nouvel utilisateur
            user_data = {
                'email': email,
                'password_hash': password_hash
            }
            result = users_collection.insert_one(user_data)
            print(f"User added with id: {result.inserted_id}")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Add or update a user in the database.')
    parser.add_argument('-email', type=str, help='The email of the user.')
    parser.add_argument('-password', type=str, help='The password of the user.')

    args = parser.parse_args()

    create_or_update_user(args.email, args.password)

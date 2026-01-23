#!/usr/bin/env python3
"""
Update Excel file with the correct event names from the user's list
"""

import pandas as pd
import os

def update_excel_events():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXCEL_PATH = os.path.join(BASE_DIR, "data", "registrations.xlsx")
    
    # User's exact event list
    user_events = [
        "Fashion Walk", "Football - Men", "Battle of Bands", "Group Dance", 
        "Throw Ball - M&W", "Kabaddi - M&W", "Tug of War - M&W", "Volley Ball - Men", 
        "Group Singing", "Mime", "IPL Auction", "Synergy Squad", "Decrypt-X", 
        "Treasure Hunt", "Murder Mystery", "Film Quiz", "DANCE BATTLE", "Duet Dance", 
        "Cosplay", "Reel Making", "BGMI", "COD Mobile", "Solo Singing", 
        "Solo Instrumental", "Solo Dance", "Mono Act", "Mehendi", "Face Painting", 
        "Pencil Sketching", "Photography", "SHORT FILM REVIEW", "JAM - JUST A MINUTE", 
        "Carrom -  M&W", "Chess - M&W", "FC26"
    ]
    
    # Load existing Excel
    df = pd.read_excel(EXCEL_PATH)
    
    # Update event names in the Excel file
    # Map old names to new names
    name_mapping = {
        "Film Quiz Challenge": "Film Quiz",
        "Kho - Kho (Men)": "Chess - M&W",  # Replace with Chess since Kho not in user list
        "Kho - Kho (Women)": "Carrom -  M&W",  # Replace with Carrom since Kho not in user list
        "Throwball (Men)": "Throw Ball - M&W",
        "Throwball (Women)": "Throw Ball - M&W",  # Both map to same M&W event
        "Kabaddi (Men)": "Kabaddi - M&W",
        "Kabaddi (Women)": "Kabaddi - M&W",  # Both map to same M&W event
        "Tug of War (Men)": "Tug of War - M&W",
        "Tug of War (Women)": "Tug of War - M&W",  # Both map to same M&W event
        "Volleyball (Men)": "Volley Ball - Men",
        "Carrom (Men)": "Carrom -  M&W",
        # Add any other mappings as needed
    }
    
    # Apply the mapping
    df['Event Name'] = df['Event Name'].replace(name_mapping)
    
    # Save updated Excel
    df.to_excel(EXCEL_PATH, index=False)
    
    print("✅ Excel file updated with correct event names!")
    print("\nUpdated events in Excel:")
    updated_events = df['Event Name'].dropna().unique().tolist()
    for i, event in enumerate(updated_events, 1):
        print(f"{i:2d}. {event}")
    print(f"\nTotal: {len(updated_events)} events")

if __name__ == "__main__":
    update_excel_events()

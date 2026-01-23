#!/usr/bin/env python3
"""
Add missing events to Excel file to match user's complete list
"""

import pandas as pd
import os

def add_missing_events():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXCEL_PATH = os.path.join(BASE_DIR, "data", "registrations.xlsx")
    
    # User's complete event list
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
    
    # Get current events
    current_events = df['Event Name'].dropna().unique().tolist()
    
    # Find missing events
    missing_events = [event for event in user_events if event not in current_events]
    
    if missing_events:
        print(f"Adding {len(missing_events)} missing events:")
        for event in missing_events:
            print(f"  - {event}")
        
        # Add missing events as empty rows (placeholder registrations)
        for event in missing_events:
            new_row = {col: "" for col in df.columns}
            new_row['Event Name'] = event
            new_row['Registration No'] = f"PLACEHOLDER_{event.replace(' ', '_').replace('-', '_')}"
            new_row['College Name'] = "PLACEHOLDER"
            new_row['Name of Team Leader'] = "PLACEHOLDER"
            
            # Append new row
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Save updated Excel
        df.to_excel(EXCEL_PATH, index=False)
        print(f"\n✅ Added {len(missing_events)} missing events to Excel file!")
    else:
        print("✅ All events already present in Excel file!")
    
    # Show final event list
    final_events = df['Event Name'].dropna().unique().tolist()
    print(f"\nFinal events in Excel ({len(final_events)} total):")
    for i, event in enumerate(sorted(final_events), 1):
        print(f"{i:2d}. {event}")

if __name__ == "__main__":
    add_missing_events()

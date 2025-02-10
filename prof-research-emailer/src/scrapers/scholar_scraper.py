import sqlite3

def search_recent_publications(professor_name):
    from scholarly import scholarly

    search_query = scholarly.search_author(professor_name)
    try:
        author = next(search_query)
        author_filled = scholarly.fill(author, sections=['publications'])
        publications = author_filled['publications']
        recent_publications = []

        for pub in publications:
            recent_publications.append({
                'title': pub['bib']['title'],
                'abstract': pub['bib'].get('abstract', 'No description available'),
                'year': pub['bib'].get('pub_year', 'Year not available')
            })

        return recent_publications
    except Exception as e:
        print(f"Error retrieving publications for {professor_name}: {e}")
        return []

def search_most_cited_publication(professor_name):
    from scholarly import scholarly

    try:
        search_query = scholarly.search_author(professor_name)
        author = next(search_query)
        author_filled = scholarly.fill(author, sections=['publications'])
        publications = author_filled['publications']

        # Find most cited publication
        most_cited = None
        max_citations = -1

        for pub in publications:
            citations = pub.get('num_citations', 0)
            if citations > max_citations:
                max_citations = citations
                most_cited = {
                    'title': pub['bib']['title'],
                    'citations': citations,
                    'year': pub['bib'].get('pub_year', 'N/A')
                }

        return most_cited

    except Exception as e:
        print(f"Error retrieving citations for {professor_name}: {e}")
        return None

def update_citation_database(professor_name, department, citation_data):
    if not citation_data:
        return

    conn = sqlite3.connect("uoft_professors.db")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR REPLACE INTO professor_citations 
            (professor_name, department, paper_title, citation_count, year)
            VALUES (?, ?, ?, ?, ?)
        """, (
            professor_name,
            department,
            citation_data['title'],
            citation_data['citations'],
            citation_data['year']
        ))
        conn.commit()
        print(f"Updated citation data for {professor_name}")
    except Exception as e:
        print(f"Error updating database: {e}")
    finally:
        conn.close()
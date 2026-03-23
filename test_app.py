# -*- coding: utf-8 -*-
# test_app.py – HorizonBoard Automatisierte Tests
import unittest
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# In-memory DB für Tests
os.environ['HorizonBoard_SECRET_KEY'] = 'test-secret'

from app import app, db, Projekt, Sprint, Epic, Aufgabe, Bug, Feedback, Kontakt


class HorizonBoardTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            p = Projekt(name='Test Projekt', kuerzel='TEST')
            db.session.add(p)
            db.session.commit()
            self.projekt_id = p.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    # ----- ROOT / DASHBOARD -----
    def test_root_redirect(self):
        """Root leitet zu erstem Projekt weiter"""
        r = self.client.get('/', follow_redirects=False)
        self.assertIn(r.status_code, [302, 200])

    def test_dashboard_ohne_projekte(self):
        """Dashboard funktioniert ohne Projekte"""
        with app.app_context():
            Projekt.query.delete()
            db.session.commit()
        r = self.client.get('/', follow_redirects=True)
        self.assertEqual(r.status_code, 200)

    # ----- AUFGABEN -----
    def test_aufgaben_board(self):
        """Aufgaben-Board lädt korrekt"""
        r = self.client.get(f'/projekt/{self.projekt_id}/aufgaben')
        self.assertEqual(r.status_code, 200)

    def test_aufgabe_erstellen(self):
        """Task-Erstellung funktioniert"""
        with app.app_context():
            s = Sprint(name='Sprint 1', projekt_id=self.projekt_id, ist_aktiv=True)
            db.session.add(s)
            db.session.commit()
            sprint_id = s.id
        r = self.client.post('/aufgabe/erstellen', data={
            'projekt_id': self.projekt_id, 'sprint_id': sprint_id,
            'titel': 'Test Aufgabe', 'status': 'Startbereit', 'prioritaet': 'Hoch',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            a = Aufgabe.query.filter_by(titel='Test Aufgabe').first()
            self.assertIsNotNone(a)
            self.assertEqual(a.prioritaet, 'Hoch')
            self.assertIsNotNone(a.aufgaben_nr)

    def test_aufgabe_detail(self):
        """Task-Detail-Seite lädt"""
        with app.app_context():
            a = Aufgabe(titel='Detail Test', projekt_id=self.projekt_id)
            db.session.add(a)
            db.session.commit()
            aid = a.id
        r = self.client.get(f'/aufgabe/{aid}/detail')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Detail Test', r.data)

    def test_api_aufgabe_status_update(self):
        """Inline-Update-API für Status"""
        with app.app_context():
            a = Aufgabe(titel='API Test', projekt_id=self.projekt_id, status='Startbereit')
            db.session.add(a)
            db.session.commit()
            aid = a.id
        r = self.client.patch(f'/api/aufgabe/{aid}',
                              data=json.dumps({'status': 'In Bearbeitung'}),
                              content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data['success'])
        with app.app_context():
            a = Aufgabe.query.get(aid)
            self.assertEqual(a.status, 'In Bearbeitung')

    def test_api_aufgabe_erledigt_setzt_erledigt_am(self):
        """Status 'Erledigt' setzt erledigt_am automatisch"""
        with app.app_context():
            a = Aufgabe(titel='Erledigt Test', projekt_id=self.projekt_id)
            db.session.add(a)
            db.session.commit()
            aid = a.id
        self.client.patch(f'/api/aufgabe/{aid}',
                          data=json.dumps({'status': 'Erledigt'}),
                          content_type='application/json')
        with app.app_context():
            a = Aufgabe.query.get(aid)
            self.assertIsNotNone(a.erledigt_am)

    def test_aufgabe_loeschen(self):
        """Task-Löschung funktioniert"""
        with app.app_context():
            a = Aufgabe(titel='Zu löschen', projekt_id=self.projekt_id)
            db.session.add(a)
            db.session.commit()
            aid = a.id
        r = self.client.post(f'/aufgabe/{aid}/loeschen',
                             data={'next_url': f'/projekt/{self.projekt_id}/aufgaben'},
                             follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            self.assertIsNone(Aufgabe.query.get(aid))

    # ----- SPRINTS -----
    def test_sprints_liste(self):
        """Sprint-Liste lädt"""
        r = self.client.get(f'/projekt/{self.projekt_id}/sprints')
        self.assertEqual(r.status_code, 200)

    def test_sprint_erstellen(self):
        """Sprint-Erstellung funktioniert"""
        r = self.client.post(f'/projekt/{self.projekt_id}/sprint/erstellen', data={
            'name': 'Sprint 1', 'ziel': 'MVP fertigstellen',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            s = Sprint.query.filter_by(name='Sprint 1').first()
            self.assertIsNotNone(s)

    def test_sprint_aktivieren(self):
        """Sprint-Aktivierung deaktiviert andere Sprints"""
        with app.app_context():
            s1 = Sprint(name='Sprint 1', projekt_id=self.projekt_id, ist_aktiv=True)
            s2 = Sprint(name='Sprint 2', projekt_id=self.projekt_id, ist_aktiv=False)
            db.session.add_all([s1, s2])
            db.session.commit()
            s1_id, s2_id = s1.id, s2.id
        self.client.post(f'/projekt/{self.projekt_id}/sprint/{s2_id}/aktivieren')
        with app.app_context():
            self.assertFalse(Sprint.query.get(s1_id).ist_aktiv)
            self.assertTrue(Sprint.query.get(s2_id).ist_aktiv)

    def test_sprint_loeschen_verschiebt_aufgaben(self):
        """Gelöschter Sprint verschiebt Aufgaben in Backlog"""
        with app.app_context():
            s = Sprint(name='Sprint X', projekt_id=self.projekt_id)
            db.session.add(s)
            db.session.commit()
            a = Aufgabe(titel='Sprint Aufgabe', projekt_id=self.projekt_id, sprint_id=s.id)
            db.session.add(a)
            db.session.commit()
            sid, aid = s.id, a.id
        self.client.post(f'/projekt/{self.projekt_id}/sprint/{sid}/loeschen')
        with app.app_context():
            self.assertIsNone(Sprint.query.get(sid))
            self.assertIsNone(Aufgabe.query.get(aid).sprint_id)

    # ----- EPICS -----
    def test_epics_liste(self):
        """Epic-Liste lädt"""
        r = self.client.get(f'/projekt/{self.projekt_id}/epics')
        self.assertEqual(r.status_code, 200)

    def test_epic_erstellen(self):
        """Epic-Erstellung funktioniert"""
        r = self.client.post(f'/projekt/{self.projekt_id}/epic/erstellen', data={
            'name': 'Test Epic', 'phase': 'Backlog', 'prioritaet': 'Hoch',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            e = Epic.query.filter_by(name='Test Epic').first()
            self.assertIsNotNone(e)
            self.assertIsNotNone(e.epic_nr)

    def test_api_epic_update(self):
        """Epic Inline-Update funktioniert"""
        with app.app_context():
            e = Epic(name='Epic API', projekt_id=self.projekt_id, phase='Backlog')
            db.session.add(e)
            db.session.commit()
            eid = e.id
        r = self.client.patch(f'/api/epic/{eid}',
                              data=json.dumps({'phase': 'Dev in Arbeit'}),
                              content_type='application/json')
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            self.assertEqual(Epic.query.get(eid).phase, 'Dev in Arbeit')

    # ----- BUGS -----
    def test_bugs_liste(self):
        """Bug-Liste lädt"""
        r = self.client.get(f'/projekt/{self.projekt_id}/bugs')
        self.assertEqual(r.status_code, 200)

    def test_bug_erstellen(self):
        """Bug-Erstellung funktioniert"""
        r = self.client.post(f'/projekt/{self.projekt_id}/bug/erstellen', data={
            'titel': 'Login-Bug', 'prioritaet': 'Kritisch', 'gruppe': 'Eingehende Bugs',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            b = Bug.query.filter_by(titel='Login-Bug').first()
            self.assertIsNotNone(b)
            self.assertIsNotNone(b.bug_nr)

    def test_api_bug_update(self):
        """Bug Inline-Update funktioniert"""
        with app.app_context():
            b = Bug(titel='Bug API Test', projekt_id=self.projekt_id, status='Prüfung ausstehend')
            db.session.add(b)
            db.session.commit()
            bid = b.id
        r = self.client.patch(f'/api/bug/{bid}',
                              data=json.dumps({'status': 'Behoben'}),
                              content_type='application/json')
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            self.assertEqual(Bug.query.get(bid).status, 'Behoben')

    # ----- RETROSPEKTIVE -----
    def test_retrospektive(self):
        """Retrospektive-Seite lädt"""
        r = self.client.get(f'/projekt/{self.projekt_id}/retrospektive')
        self.assertEqual(r.status_code, 200)

    def test_feedback_erstellen(self):
        """Feedback-Erstellung funktioniert"""
        with app.app_context():
            s = Sprint(name='Sprint 1', projekt_id=self.projekt_id, ist_aktiv=True)
            db.session.add(s)
            db.session.commit()
            sid = s.id
        r = self.client.post(f'/projekt/{self.projekt_id}/feedback/erstellen', data={
            'inhalt': 'Gute Zusammenarbeit!', 'typ': 'Behalten', 'sprint_id': sid,
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            f = Feedback.query.filter_by(inhalt='Gute Zusammenarbeit!').first()
            self.assertIsNotNone(f)
            self.assertEqual(f.typ, 'Behalten')

    def test_feedback_abstimmen(self):
        """Feedback-Voting funktioniert"""
        with app.app_context():
            f = Feedback(inhalt='Voting Test', projekt_id=self.projekt_id, abstimmung=2)
            db.session.add(f)
            db.session.commit()
            fid = f.id
        r = self.client.post(f'/feedback/{fid}/abstimmen')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['abstimmung'], 3)

    # ----- KONTAKTE -----
    def test_kontakte_liste(self):
        """Kontakte-Liste lädt"""
        r = self.client.get('/kontakte')
        self.assertEqual(r.status_code, 200)

    def test_kontakt_erstellen(self):
        """Kontakt-Erstellung funktioniert"""
        r = self.client.post('/kontakt/neu', data={
            'name': 'Max Mustermann', 'email': 'max@test.de', 'firma': 'Test GmbH',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            k = Kontakt.query.filter_by(name='Max Mustermann').first()
            self.assertIsNotNone(k)

    # ----- PROJEKT -----
    def test_projekt_erstellen(self):
        """Projekt-Erstellung mit automatischem Sprint"""
        r = self.client.post('/projekt/neu', data={
            'name': 'Neues Projekt', 'kuerzel': 'NEU',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            p = Projekt.query.filter_by(name='Neues Projekt').first()
            self.assertIsNotNone(p)
            # Automatischer Sprint sollte erstellt worden sein
            self.assertEqual(p.sprints.count(), 1)
            self.assertTrue(p.sprints.first().ist_aktiv)

    def test_kanban_ansicht(self):
        """Kanban-Ansicht lädt"""
        r = self.client.get(f'/projekt/{self.projekt_id}/aufgaben/kanban')
        self.assertEqual(r.status_code, 200)


if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(HorizonBoardTestCase)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


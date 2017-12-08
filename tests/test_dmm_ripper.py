import unittest
import os, sys

parentPath = os.path.abspath('..')
if parentPath not in sys.path:
    sys.path.insert(0, parentPath)
    import dmm_ripper as dmm

class TestDMMRipper(unittest.TestCase):
    
    hardcoded_login_url = 'https://www.dmm.com/my/-/login/' \
            + '=/path=DRVESRUMTh1aCl5THVILWk8GWVsf/channel=book'

    email = 'fake_email@real_fake_email.com'
    password = 'th1s1sf4k3p455'
    valid_account = False

    def test_get_login_url(self):
        url = dmm.get_login_url(True)
        self.assertEqual(self.hardcoded_login_url, url)

        dynamic_url = dmm.get_login_url(False)
        self.assertEqual(self.hardcoded_login_url, dynamic_url)

    def test_get_dmm_session(self):
        session = None
        try:
            session = dmm.get_session(
                TestDMMRipper.email,
                TestDMMRipper.password,
                fast=True
            )
        except:
            pass
        finally:
            if not TestDMMRipper.valid_account:
                self.assertEqual(session, None)
            else:
                self.assertNotEqual(session, None)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        TestDMMRipper.password = sys.argv.pop()
        TestDMMRipper.email = sys.argv.pop()
        TestDMMRipper.valid_account = True
    unittest.main()
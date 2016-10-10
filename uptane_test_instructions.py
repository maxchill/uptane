# The code below is intended to be run IN THREE PYTHON SHELLS:
# - One for the Main Repository ("supplier")
# - One for the Director Repository
# - One for the client

# Each shell should be run in a python environment (the same environment is
# fine) that has the awwad/tuf:pinning version of TUF installed. In order to
# get everything you need, run the following:
# `pip install cffi==1.7.0 pycrypto==2.6.1 pynacl==1.0.1 cryptography`
# `pip install git+git://github.com/awwad/tuf.git@pinning`

# If you're going to be running the ASN.1 encoding scripts (not involved here),
# you'll also need to `pip install pyasn1`

# In each python window, run:
#   import uptane_test_instructions as u

# Then run the following:
# In the mainrepo's window:
#   u.mainrepo()

# In the director's window:
#   u.director()

# In the client's window:
# (AFTER THE OTHER TWO HAVE FINISHED STARTING UP AND ARE HOSTING)
#   u.client()


# ----------------
# Main repo window
# ----------------

def mainrepo(use_new_keys=False):

  import os
  import sys, subprocess, time # For hosting and arguments
  import tuf.repository_tool as rt
  import shutil # for rmtree

  WORKING_DIR = os.getcwd()
  MAIN_REPO_DIR = os.path.join(WORKING_DIR, 'repomain')
  TARGETS_DIR = os.path.join(MAIN_REPO_DIR, 'targets')
  MAIN_REPO_HOST = 'http://localhost'
  MAIN_REPO_PORT = 30300


  # Whether to use existing keys or create new ones, an argument to the script.
  # (If you just copy-paste all this code in a python shell, you'll get False and
  #  use existing keys, so have the key files or override this value.)

  #use_new_keys = len(sys.argv) == 2 and sys.argv[1] == '--newkeys'


  # Create target files: file1.txt and file2.txt

  if os.path.exists(TARGETS_DIR):
    shutil.rmtree(TARGETS_DIR)

  os.makedirs(TARGETS_DIR)

  fobj = open(os.path.join(TARGETS_DIR, 'file1.txt'), 'w')
  fobj.write('Contents of file1.txt')
  fobj.close()
  fobj = open(os.path.join(TARGETS_DIR, 'file2.txt'), 'w')
  fobj.write('Contents of file2.txt')
  fobj.close()


  # Create repo at './repomain'

  repomain = rt.create_new_repository('repomain')


  # Create keys and/or load keys into memory.

  if use_new_keys:
    rt.generate_and_write_ed25519_keypair('mainroot', password='pw')
    rt.generate_and_write_ed25519_keypair('maintimestamp', password='pw')
    rt.generate_and_write_ed25519_keypair('mainsnapshot', password='pw')
    rt.generate_and_write_ed25519_keypair('maintargets', password='pw')
    rt.generate_and_write_ed25519_keypair('mainrole1', password='pw')

  key_root_pub = rt.import_ed25519_publickey_from_file('mainroot.pub')
  key_root_pri = rt.import_ed25519_privatekey_from_file('mainroot', password='pw')
  key_timestamp_pub = rt.import_ed25519_publickey_from_file('maintimestamp.pub')
  key_timestamp_pri = rt.import_ed25519_privatekey_from_file('maintimestamp', password='pw')
  key_snapshot_pub = rt.import_ed25519_publickey_from_file('mainsnapshot.pub')
  key_snapshot_pri = rt.import_ed25519_privatekey_from_file('mainsnapshot', password='pw')
  key_targets_pub = rt.import_ed25519_publickey_from_file('maintargets.pub')
  key_targets_pri = rt.import_ed25519_privatekey_from_file('maintargets', password='pw')
  key_role1_pub = rt.import_ed25519_publickey_from_file('mainrole1.pub')
  key_role1_pri = rt.import_ed25519_privatekey_from_file('mainrole1', password='pw')


  # Add top level keys to the main repository.

  repomain.root.add_verification_key(key_root_pub)
  repomain.timestamp.add_verification_key(key_timestamp_pub)
  repomain.snapshot.add_verification_key(key_snapshot_pub)
  repomain.targets.add_verification_key(key_targets_pub)
  repomain.root.load_signing_key(key_root_pri)
  repomain.timestamp.load_signing_key(key_timestamp_pri)
  repomain.snapshot.load_signing_key(key_snapshot_pri)
  repomain.targets.load_signing_key(key_targets_pri)


  # Perform delegation from mainrepo's targets role to mainrepo's role1 role.

  repomain.targets.delegate('role1', [key_role1_pub],
      ['repomain/targets/file1.txt', 'repomain/targets/file2.txt'],
      threshold=1, backtrack=True,
      restricted_paths=[os.path.join(TARGETS_DIR, 'file*.txt')])


  # Add delegated role keys to repo

  repomain.targets('role1').load_signing_key(key_role1_pri)


  # Write the metadata files out to mainrepo's 'metadata.staged'

  repomain.write()


  # Move staged metadata (from the write above) to live metadata directory.

  if os.path.exists(os.path.join(MAIN_REPO_DIR, 'metadata')):
    shutil.rmtree(os.path.join(MAIN_REPO_DIR, 'metadata'))

  shutil.copytree(
      os.path.join(MAIN_REPO_DIR, 'metadata.staged'),
      os.path.join(MAIN_REPO_DIR, 'metadata'))



  # Prepare to host the main repo contents

  os.chdir(MAIN_REPO_DIR)

  command = []
  if sys.version_info.major < 3:  # Python 2 compatibility
    command = ['python', '-m', 'SimpleHTTPServer', str(MAIN_REPO_PORT)]
  else:
    command = ['python', '-m', 'http.server', str(MAIN_REPO_PORT)]

  # Begin hosting mainrepo.

  server_process = subprocess.Popen(command, stderr=subprocess.PIPE)
  print('Main Repo server process started.')
  print('Main Repo server process id: ' + str(server_process.pid))
  print('Main Repo serving on port: ' + str(MAIN_REPO_PORT))
  url = MAIN_REPO_HOST + ':' + str(MAIN_REPO_PORT) + '/'
  print('Main Repo URL is: ' + url)

  # Wait / allow any exceptions to kill the server.

  try:
    time.sleep(10000) # Stop hosting after a while.
  except:
    print('Exception caught')
    pass
  finally:
    if server_process.returncode is None:
      print('Terminating Main Repo server process ' + str(server_process.pid))
      server_process.kill()





# ----------------
# Director window
# ----------------

def director(use_new_keys=False):
  import os # For paths and symlink
  import shutil # For copying directory trees
  import sys, subprocess, time # For hosting
  import tuf.repository_tool as rt


  WORKING_DIR = os.getcwd()
  MAIN_REPO_DIR = os.path.join(WORKING_DIR, 'repomain')
  DIRECTOR_REPO_DIR = os.path.join(WORKING_DIR, 'repodirector')
  TARGETS_DIR = os.path.join(MAIN_REPO_DIR, 'targets')
  DIRECTOR_REPO_HOST = 'http://localhost'
  DIRECTOR_REPO_PORT = 30301

  #use_new_keys = len(sys.argv) == 2 and sys.argv[1] == '--newkeys'


  # Create repo at './repodirector'

  repodirector = rt.create_new_repository('repodirector')


  # Create keys and/or load keys into memory.

  if use_new_keys:
    rt.generate_and_write_ed25519_keypair('directorroot', password='pw')
    rt.generate_and_write_ed25519_keypair('directortimestamp', password='pw')
    rt.generate_and_write_ed25519_keypair('directorsnapshot', password='pw')
    rt.generate_and_write_ed25519_keypair('director', password='pw') # targets


  key_dirroot_pub = rt.import_ed25519_publickey_from_file('directorroot.pub')
  key_dirroot_pri = rt.import_ed25519_privatekey_from_file('directorroot', password='pw')
  key_dirtime_pub = rt.import_ed25519_publickey_from_file('directortimestamp.pub')
  key_dirtime_pri = rt.import_ed25519_privatekey_from_file('directortimestamp', password='pw')
  key_dirsnap_pub = rt.import_ed25519_publickey_from_file('directorsnapshot.pub')
  key_dirsnap_pri = rt.import_ed25519_privatekey_from_file('directorsnapshot', password='pw')
  key_dirtarg_pub = rt.import_ed25519_publickey_from_file('director.pub')
  key_dirtarg_pri = rt.import_ed25519_privatekey_from_file('director', password='pw')


  # Add top level keys to the main repository.

  repodirector.root.add_verification_key(key_dirroot_pub)
  repodirector.timestamp.add_verification_key(key_dirtime_pub)
  repodirector.snapshot.add_verification_key(key_dirsnap_pub)
  repodirector.targets.add_verification_key(key_dirtarg_pub)
  repodirector.root.load_signing_key(key_dirroot_pri)
  repodirector.timestamp.load_signing_key(key_dirtime_pri)
  repodirector.snapshot.load_signing_key(key_dirsnap_pri)
  repodirector.targets.load_signing_key(key_dirtarg_pri)


  # Add target to director.
  # FOR NOW, we symlink the targets files on the director.
  # In the future, we probably have to have the repository tools add a function
  # like targets.add_target_from_metadata that doesn't require an actual target
  # file to exist, but instead provides metadata on some hypothetical file that
  # the director may not physically hold.
  if os.path.exists(os.path.join(DIRECTOR_REPO_DIR, 'targets', 'file2.txt')):
    os.remove(os.path.join(DIRECTOR_REPO_DIR, 'targets', 'file2.txt'))

  os.symlink(os.path.join(TARGETS_DIR, 'file2.txt'),
      os.path.join(DIRECTOR_REPO_DIR, 'targets', 'file2.txt'))

  repodirector.targets.add_target(
      os.path.join(DIRECTOR_REPO_DIR, 'targets', 'file2.txt'),
      custom={"ecu-serial-number": "some_ecu_serial", "type": "application"})


  # Write to director repo's metadata.staged.
  repodirector.write()


  # Move staged metadata (from the write) to live metadata directory.

  if os.path.exists(os.path.join(DIRECTOR_REPO_DIR, 'metadata')):
    shutil.rmtree(os.path.join(DIRECTOR_REPO_DIR, 'metadata'))

  shutil.copytree(
      os.path.join(DIRECTOR_REPO_DIR, 'metadata.staged'),
      os.path.join(DIRECTOR_REPO_DIR, 'metadata'))


  # Prepare to host the director repo contents.

  os.chdir(DIRECTOR_REPO_DIR)

  command = []
  if sys.version_info.major < 3: # Python 2 compatibility
    command = ['python', '-m', 'SimpleHTTPServer', str(DIRECTOR_REPO_PORT)]
  else:
    command = ['python', '-m', 'http.server', str(DIRECTOR_REPO_PORT)]

  # Begin hosting the director's repository.

  server_process = subprocess.Popen(command, stderr=subprocess.PIPE)
  print('Director repo server process started.')
  print('Director repo server process id: ' + str(server_process.pid))
  print('Director repo serving on port: ' + str(DIRECTOR_REPO_PORT))
  url = DIRECTOR_REPO_HOST + ':' + str(DIRECTOR_REPO_PORT) + '/'
  print('Director repo URL is: ' + url)

  # Wait / allow any exceptions to kill the server.

  try:
    time.sleep(10000) # Stop hosting after a while.
  except:
    print('Exception caught')
    pass
  finally:
    if server_process.returncode is None:
      print('Terminating Director repo server process ' + str(server_process.pid))
      server_process.kill()





# ----------------
# Client window
# ----------------

def client(use_new_keys=False):
  # Make client directory and copy the root file from the repository.
  import os # For paths and makedirs
  import shutil # For copyfile
  import tuf.client.updater
  import tuf.repository_tool as rt
  import tuf.keys

  WORKING_DIR = os.getcwd()
  CLIENT_DIR = os.path.join(WORKING_DIR, 'clientane')
  CLIENT_METADATA_DIR_MAINREPO_CURRENT = os.path.join(CLIENT_DIR, 'metadata', 'mainrepo', 'current')
  CLIENT_METADATA_DIR_MAINREPO_PREVIOUS = os.path.join(CLIENT_DIR, 'metadata', 'mainrepo', 'previous')
  CLIENT_METADATA_DIR_DIRECTOR_CURRENT = os.path.join(CLIENT_DIR, 'metadata', 'director', 'current')
  CLIENT_METADATA_DIR_DIRECTOR_PREVIOUS = os.path.join(CLIENT_DIR, 'metadata', 'director', 'previous')
  CLIENT_STUBREPO_DIR = os.path.join(CLIENT_DIR, 'stubrepos', '')

  # Note that the hosts and ports are drawn from pinned.json now.

  MAIN_REPO_DIR = os.path.join(WORKING_DIR, 'repomain')
  TARGETS_DIR = os.path.join(MAIN_REPO_DIR, 'targets')
  #MAIN_REPO_HOST = 'http://localhost'
  #MAIN_REPO_PORT = 30300
  DIRECTOR_REPO_DIR = os.path.join(WORKING_DIR, 'repodirector')
  #DIRECTOR_REPO_HOST = 'http://localhost'
  #DIRECTOR_REPO_PORT = 30301

  if os.path.exists(CLIENT_DIR):
    shutil.rmtree(CLIENT_DIR)

  for d in [
      CLIENT_METADATA_DIR_MAINREPO_CURRENT,
      CLIENT_METADATA_DIR_MAINREPO_PREVIOUS,
      CLIENT_METADATA_DIR_DIRECTOR_CURRENT,
      CLIENT_METADATA_DIR_DIRECTOR_PREVIOUS]:
    os.makedirs(d)

  # Get the root.json file from the mainrepo (would come with this client).
  shutil.copyfile(
      os.path.join(MAIN_REPO_DIR, 'metadata.staged', 'root.json'),
      os.path.join(CLIENT_METADATA_DIR_MAINREPO_CURRENT, 'root.json'))

  # Get the root.json file from the director repo (would come with this client).
  shutil.copyfile(
      os.path.join(DIRECTOR_REPO_DIR, 'metadata.staged', 'root.json'),
      os.path.join(CLIENT_METADATA_DIR_DIRECTOR_CURRENT, 'root.json'))

  # Add a pinned.json to this client (softlink it from a saved copy).
  os.symlink(
      os.path.join(WORKING_DIR, 'pinned.json'),
      os.path.join(CLIENT_DIR, 'metadata', 'pinned.json'))

  # Configure tuf with the client's metadata directories (where it stores the
  # metadata it has collected from each repository, in subdirectories).
  tuf.conf.repository_directory = CLIENT_DIR # This setting should probably be called client_directory instead, post-TAP4.

  # Create a TAP-4-compliant updater object. This will read pinning.json
  # and create single-repository updaters within it to handle connections to
  # each repository.
  upd = tuf.client.updater.Updater('updater')

  # Starting with just the root.json files for the director and mainrepo, and
  # pinned.json, the client will now use TUF to connect to each repository and
  # download/update top-level metadata. This call updates metadata from both
  # repositories.
  upd.refresh()

  # This call determines what the right fileinfo (hash, length, etc) for
  # target file file2.txt is. This begins by matching paths/patterns in
  # pinned.json to determine which repository to connect to. Since pinned.json
  # in this case assigns all targets to a multi-repository delegation requiring
  # consensus between the two repos "director" and "mainrepo", this call will
  # retrieve metadata from both repositories and compare it to each other, and
  # only return fileinfo if it can be retrieved from both repositories and is
  # identical (the metadata in the "custom" fileinfo field need not match, and
  # should not, since the Director will include ECU IDs in this field, and the
  # mainrepo cannot.
  # In this particular case, fileinfo will match and be stored, since both
  # repositories list file2.txt as a target, and they both have matching metadata
  # for it.
  file2_trustworthy_info = upd.target('file2.txt')

  # If you execute the following, commented-out command, you'll get a not found
  # error, because while the mainrepo specifies file1.txt, the Director does not.
  # Anything the Director doesn't also list can't be validated.
  # file1_trustworthy_info = upd.target('file1.txt')

  # Delete file2.txt if it already exists.
  if os.path.exists('./file2.txt'):
    os.remove('./file2.txt')

  # Now that we have fileinfo for file2.txt, matching the Director and mainrepo
  # (Supplier), we can download the file and only keep it if it matches that
  # fileinfo. This call will try every mirror on every repository within the
  # appropriate delegation in pinned.json until one of them works. In this case,
  # both the Director and mainrepo (Supplier) are hosting the file, just for my
  # convenience in setup. If you remove the file from the Director before calling
  # this, it will still work (assuming mainrepo still has it).
  # (The second argument here is just where to put the file.)

  upd.download_target(file2_trustworthy_info, '.')

  if os.path.exists('./file2.txt'):
    print('File file2.txt has successfully been validated and downloaded.')
  else:
    print('Nope, file2.txt was not downloaded.')
    assert False

  # Test installing the firmware.

  # Here, I'll assume that the client retains metadata about the firmware image
  # it currently has installed. Things could operate instead such that metadata
  # is calculated based on the installed image.
  # For this test, we'll assume that the target info provided by the Director
  # and supplier for file2 is the same as what is already running on the
  # client.

  # This is a tuf.formats.TARGETFILE_SCHEMA, containing filepath and fileinfo
  # fields.
  installed_firmware_targetinfo = file2_trustworthy_info



  signed_ecu_manifest = generate_signed_ecu_manifest(
      installed_firmware_targetinfo)



  def generate_signed_ecu_manifest(installed_firmware_targetinfo):
    """
    Takes a tuf.formats.TARGETFILE_SCHEMA (the target info for the firmware on
    an ECU) and returns a signed ECU manifest indicating that target file info,
    encoded in BER (requires code added to two ber_* functions below).
    """

    # We'll construct a signed signable_ecu_manifest_SCHEMA from the
    # targetinfo.
    # First, construct and check an ECU_VERSION_MANIFEST_SCHEMA.
    ecu_manifest = {
        'installed_image': installed_firmware_targetinfo,
        'timeserver_time': '2016-10-10T11:37:30Z',
        'previous_timeserver_time': '2016-10-10T11:37:30Z',
        'attacks_detected': ''
    }
    uptane.formats.ECU_VERSION_MANIFEST_SCHEMA.check_match(ecu_manifest)

    # Now we'll convert it into a signable object and sign it with a key we
    # generate.

    if use_new_keys:
      rt.generate_and_write_ed25519_keypair('secondary', password='pw')

    # Load in from the generated files.
    key_pub = rt.import_ed25519_publickey_from_file('secondary.pub')
    key_pri = rt.import_ed25519_privatekey_from_file('secondary', password='pw')

    # Turn this into a canonical key matching tuf.formats.ANYKEY_SCHEMA
    key = {
        'keytype': key_pub['keytype'],
        'keyid': key_pub['keyid'],
        'keyval': {'public': key_pub['public'], 'private': key_pri['private']}}
    tuf.formats.ANYKEY_SCHEMA.check_match(key)

    # TODO: Once the ber encoder functions are done, do this:
    original_ecu_manifest = ecu_manifest
    ecu_manifest = ber_encode_ecu_manifest(ecu_manifest)

    # Wrap the ECU version manifest object into an
    # uptane.formats.signable_ecu_manifest and check the format.
    # {
    #     'signed': ecu_version_manifest,
    #     'signatures': []
    # }
    signable_ecu_manifest = tuf.formats.make_signable(
        ecu_manifest)
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signable_ecu_manifest)

    # Now sign with that key. (Also do ber encoding of the signed portion.)
    signed_ecu_manifest = sign_signable(ecu_manifest, [key])
    tuf.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signed_ecu_manifest)

    # TODO: Once the ber encoder functions are done, do this:
    original_signed_ecu_manifest = signed_ecu_manifest
    ber_encoded_signed_ecu_manifest = ber_encode_signable_content(signed_ecu_manifest)

    return ber_encoded_signed_ecu_manifest



def ber_encode_signable_content(signable):
  print('SKIPPING BER ENCODING OF SIGNABLE!!!')
  return signable

def ber_encode_ecu_manifest(ecu_manifest):
  print('SKIPPING BER ENCODING OF ECU MANIFEST!!!')
  return ecu_manifest



def sign_signable(signable, keys_to_sign_with):
  """
  Signs the given signable (e.g. an ECU manifest) with all the given keys.

  Arguments:

    signable:
      An object with a 'signed' dictionary and a 'signatures' list:
      conforms to tuf.formats.SIGNABLE_SCHEMA

    keys_to_sign_with:
      A list whose elements must conform to tuf.formats.ANYKEY_SCHEMA.

  Returns:

    A signable object (tuf.formats.SIGNABLE_SCHEMA), but with the signatures
    added to its 'signatures' list.

  """

  # The below was partially modeled after tuf.repository_lib.sign_metadata()

  signatures = []

  for signing_key in keys_to_sign_with:
    
    tuf.formats.ANYKEY_SCHEMA.check_match(signing_key)

    # If we already have a signature with this keyid, skip.
    if signing_key['keyid'] in [key['keyid'] for key in signatures]:
      print('Already signed with this key.')
      continue

    # If the given key was public, raise a FormatError.
    if 'private' not in signing_key['keyval']:
      raise tuf.FormatError('One of the given keys lacks a private key value, '
          'and so cannot be used for signing: ' + repr(signing_key))
    
    # We should already be guaranteed to have a supported key type due to
    # the ANYKEY_SCHEMA.check_match call above. Defensive programming.
    if signing_key['keytype'] not in SUPPORTED_KEY_TYPES:
      assert False, 'Programming error: key types have already been ' + \
          'validated; should not be possible that we now have an ' + \
          'unsupported key type, but we do: ' + repr(signing_key['keytype'])


    # Else, all is well. Sign the signable with the given key, adding that
    # signature to the signatures list in the signable.
    signable['signatures'].append(
        tuf.keys.create_signature(signing_key, signable['signed']))


  # Confirm that the formats match what is expected post-signing, including a
  # check again for SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA. Raise
  # 'tuf.FormatError' if the format is wrong.

  tuf.formats.check_signable_object_format(signable)

  return signable # Fully signed






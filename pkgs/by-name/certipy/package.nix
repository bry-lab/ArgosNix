# Worked example of a tier-2 package: pure Python, normal pyproject, no build
# system heroics. Most of the backlog looks like this, which is why tier 2 is
# where the throughput is.
#
# Generated skeleton from `argos new certipy --builder python`, hashes filled
# in by `nix-init --url https://github.com/ly4k/Certipy`.
#
# NOTE: the hash below is still lib.fakeHash, so this does not build yet. The
# catalog entry deliberately does NOT set `local = "certipy"` until it does --
# claiming a package that fails to build would inflate the coverage number,
# which is the one number in this repo that has to stay honest. `argos
# validate` warns about the gap until you close it.
{ lib
, python3Packages
, fetchFromGitHub
}:

python3Packages.buildPythonApplication rec {
  pname = "certipy";
  version = "4.8.2";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "ly4k";
    repo = "Certipy";
    tag = "${version}";
    # Replace with the real hash: nix-prefetch-github ly4k Certipy --rev 4.8.2
    hash = lib.fakeHash;
  };

  build-system = with python3Packages; [ setuptools ];

  dependencies = with python3Packages; [
    asn1crypto
    cryptography
    impacket
    ldap3
    pyasn1
    pycryptodome
    pyopenssl
    requests
    requests-ntlm
    unicrypto
  ];

  # No test suite worth running, and what exists wants a live domain
  # controller. Import check is the useful signal here.
  doCheck = false;
  pythonImportsCheck = [ "certipy" ];

  meta = with lib; {
    description = "Active Directory Certificate Services enumeration and abuse";
    homepage = "https://github.com/ly4k/Certipy";
    license = licenses.mit;
    mainProgram = "certipy";
    maintainers = with maintainers; [ ];
    platforms = platforms.unix;
  };
}

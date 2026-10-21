"""Install a manifest-verified NeutralMean7 .qstrat ZIP into a Freqtrade user directory."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import zipfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('package',type=Path)
    parser.add_argument('--userdir',required=True,type=Path)
    args=parser.parse_args()
    destination=args.userdir.resolve()
    with zipfile.ZipFile(args.package) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        assert manifest['format']=='freqtrade-qstrat-bundle' and manifest['version']==1
        files=manifest['files'];names=set(archive.namelist())
        assert names==set(files)|{'manifest.json'},'Unmanifested or missing archive entry'
        prepared=[]
        for name,expected in files.items():
            relative=PurePosixPath(name)
            assert not relative.is_absolute() and '..' not in relative.parts and '\\' not in name
            data=archive.read(name)
            assert hashlib.sha256(data).hexdigest()==expected, f'Checksum mismatch: {name}'
            if name.startswith('payload/'):
                target=(destination/Path(*relative.parts[1:])).resolve()
                assert target.is_relative_to(destination)
                if target.exists() and target.read_bytes()!=data:
                    raise FileExistsError(f'Refusing to overwrite different file: {target}')
                prepared.append((target,data))
        # All paths/hashes/conflicts are checked before the first write.
        for target,data in prepared:
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        print(json.dumps({'installed':len(prepared),'userdir':str(destination),
            'strategy':'NeutralMean7Portable','package_sha256':hashlib.sha256(args.package.read_bytes()).hexdigest()},ensure_ascii=False))


if __name__=='__main__':main()

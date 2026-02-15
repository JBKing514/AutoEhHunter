package LANraragi::Plugin::Metadata::EhViewerFile;

use strict;
use warnings;
no warnings 'uninitialized';
use utf8;

use Mojo::JSON qw(decode_json);
use Mojo::Util qw(html_unescape);
use Mojo::DOM;

use LANraragi::Utils::Archive qw(is_file_in_archive extract_file_from_archive);
use LANraragi::Utils::Logging qw(get_plugin_logger);

# Simple in-process cache for the tag translation database.
our %DB_CACHE;

# Meta-information about your plugin.
sub plugin_info {

    return (
        name       => "EhViewer .ehviewer",
        type       => "metadata",
        namespace  => "ehviewerfile",
        login_from => "ehlogin",
        author     => "OpenCode (based on EHentai/ETagCN plugins)",
        version    => "1.0.4",
        description =>
          "Extracts EH gID/token from embedded metadata files (.ehviewer, metadata JSON, ComicInfo.xml) and fetches tags through the E-Hentai API. Optionally translates E-H tags to Chinese using an EhTagTranslation db.text.json.",
        # Named parameters (hash style) so settings are saved reliably.
        parameters => {
            savetitle => {
                type          => "bool",
                desc          => "保存 E-H 标题为档案标题（需要允许替换标题）",
                default_value => 0
            },
            jpntitle => {
                type          => "bool",
                desc          => "如果可用，使用日文原标题 (title_jpn)",
                default_value => 0
            },
            additionaltags => {
                type          => "bool",
                desc          => "添加额外元数据标签（uploader、timestamp、category）",
                default_value => 0
            },
            useexh => {
                type          => "bool",
                desc          => "添加 source:exhentai.org/...（否则为 e-hentai.org）",
                default_value => 0
            },
            db_path => {
                type          => "string",
                desc          => "EhTagTranslation 项目的 JSON 数据库文件(db.text.json)的绝对路径（留空则不翻译）",
                default_value => ""
            },
        },
        # Upgrade path from old positional (customargs) config.
        to_named_params => [qw(savetitle jpntitle additionaltags useexh db_path)],
        cooldown => 2
    );
}

# Mandatory function to be implemented by your plugin
sub get_tags {

    shift;
    my $lrr_info = shift;    # Global info hash

    # Support both old positional params and new named params.
    my ( $savetitle, $jpntitle, $additionaltags, $useexh, $db_path ) = ( 0, 0, 0, 0, "" );
    if ( @_ == 1 && ref( $_[0] ) eq 'HASH' ) {
        my $p = $_[0];
        $savetitle      = $p->{savetitle}      // 0;
        $jpntitle       = $p->{jpntitle}       // 0;
        $additionaltags = $p->{additionaltags} // 0;
        $useexh         = $p->{useexh}         // 0;
        $db_path        = $p->{db_path}        // "";
    } else {
        ( $savetitle, $jpntitle, $additionaltags, $useexh, $db_path ) = @_;
    }

    my $logger = get_plugin_logger();

    my ( $gid, $token, $source_hint ) = _extract_gid_token_from_archive( $lrr_info->{file_path} );
    die "Could not extract gID/token from embedded metadata\n" if ( !$gid || !$token );
    $logger->debug("Extracted gID/token from $source_hint: $gid / $token");

    # Fetch EH metadata
    my ( $tags_ref, $title_ref ) = _get_tags_from_eh_api( $lrr_info->{user_agent}, $gid, $token, $jpntitle, $additionaltags );

    # Translate tags if a db path was provided
    my $final_tags_ref = $tags_ref;
    if ( defined($db_path) && $db_path ne "" ) {
        $final_tags_ref = _translate_tag_to_cn( $tags_ref, $db_path );
    }

    # Add source tag from parsed gID/token
    my $domain = $useexh ? 'exhentai.org' : 'e-hentai.org';
    push( @$final_tags_ref, "source:$domain/g/$gid/$token" );

    my $tags = join( ", ", @$final_tags_ref );
    $logger->info("Sending the following tags to LRR: $tags");

    my %ret = ( tags => $tags );
    if ($savetitle) {
        $ret{title} = $$title_ref;
    }

    return %ret;
}

sub _extract_gid_token_from_archive {

    my ($archive_path) = @_;
    my $logger = get_plugin_logger();

    # Try EhViewer's plain-text file first
    # Match both ".ehviewer" and "ehviewer" (case-insensitive)
    my $path_in_archive = is_file_in_archive( $archive_path, "(?i:\\.?ehviewer)" );
    if ($path_in_archive) {
        my $filepath = extract_file_from_archive( $archive_path, $path_in_archive );
        my ( $gid, $token ) = _parse_ehviewer_file($filepath);
        unlink $filepath if ( -e $filepath );
        return ( $gid, $token, ".ehviewer" ) if ( $gid && $token );
        $logger->warn("Found .ehviewer but couldn't parse gID/token");
    }

    # Then try a JSON file named exactly "metadata" (common in some downloaders)
    $path_in_archive = is_file_in_archive( $archive_path, "(?i:metadata)" );
    if ($path_in_archive) {
        my $filepath = extract_file_from_archive( $archive_path, $path_in_archive );
        my ( $gid, $token ) = _parse_metadata_json_file($filepath);
        unlink $filepath if ( -e $filepath );
        return ( $gid, $token, "metadata" ) if ( $gid && $token );
        $logger->warn("Found metadata JSON but couldn't parse gID/token");
    }

    # Finally, ComicInfo.xml (Web field may include the EH URL)
    $path_in_archive = is_file_in_archive( $archive_path, "(?i:ComicInfo\\.xml)" );
    if ($path_in_archive) {
        my $filepath = extract_file_from_archive( $archive_path, $path_in_archive );
        my ( $gid, $token ) = _parse_comicinfo_file($filepath);
        unlink $filepath if ( -e $filepath );
        return ( $gid, $token, "ComicInfo.xml" ) if ( $gid && $token );
        $logger->warn("Found ComicInfo.xml but couldn't parse gID/token");
    }

    return ( "", "", "" );
}

sub _parse_ehviewer_file {

    my ($filepath) = @_;
    my $logger = get_plugin_logger();

    open( my $fh, '<:raw', $filepath ) or die "Could not open $filepath\n";
    local $/;
    my $data = <$fh>;
    close($fh);

    # EhViewer stores two different formats in the wild:
    # - Legacy plaintext (usually starts with VERSION2)
    # - Binary CBOR map (often starts with 0xBF, contains keys like gid/token/pages/pTokenMap)
    #
    # To avoid regressions, always try the plaintext parser first (it won't match on binary CBOR),
    # then fall back to CBOR.

    my ( $gid, $token, $pagehashes_ref ) = _parse_ehviewer_legacy_text($data);
    return ( $gid, $token, $pagehashes_ref ) if ( $gid && $token );

    ( $gid, $token ) = _parse_ehviewer_cbor($data);
    return ( $gid, $token, [] ) if ( $gid && $token );

    return ( "", "", [] );
}

sub _parse_ehviewer_legacy_text {

    my ($data) = @_;
    my $logger = get_plugin_logger();

    return ( "", "", [] ) if ( !defined($data) || $data eq "" );

    # Strip UTF-8 BOM if present
    if ( substr( $data, 0, 3 ) eq "\xEF\xBB\xBF" ) {
        $data = substr( $data, 3 );
    }

    # Support \n, \r\n and \r newlines
    my @lines = split( /\r\n|\n|\r/, $data );
    @lines = map {
        my $l = $_;
        $l =~ s/^\s+//;
        $l =~ s/\s+$//;
        $l;
    } @lines;

    my $gid   = "";
    my $token = "";

    # Fast path: standard EhViewer plaintext (VERSION2 ...)
    if ( @lines >= 4 && $lines[0] =~ /^VERSION\d*$/ ) {
        $gid   = $lines[2] if ( $lines[2] =~ /^\d+$/ );
        $token = $lines[3] if ( $lines[3] =~ /^[0-9a-fA-F]{10}$/ );
    }

    # Fallback: look for an EH URL in the file (some tools embed it)
    if ( !$gid || !$token ) {
        foreach my $l (@lines) {
            if ( $l =~ m{/g/(\d+)/(\w+)/?} ) {
                $gid   = $1;
                $token = $2;
                last;
            }
        }
    }

    # Fallback: scan for (gid line) then (token line)
    if ( !$gid || !$token ) {
        for ( my $i = 0; $i < @lines - 1; $i++ ) {
            next unless $lines[$i] =~ /^\d+$/;
            next unless $lines[ $i + 1 ] =~ /^[0-9a-fA-F]{10}$/;
            $gid   = $lines[$i];
            $token = $lines[ $i + 1 ];
            last;
        }
    }

    # Parse per-page image hashes (the 10-char keys used in /s/<hash>/ URLs)
    my @pagehashes;
    foreach my $l (@lines) {
        # Example: "0 7365785783"
        if ( $l =~ /^\d+\s+([0-9a-zA-Z]{10})$/ ) {
            push @pagehashes, $1;
        }
    }

    $logger->debug(".ehviewer page hash count: " . scalar(@pagehashes)) if @pagehashes;
    return ( $gid, $token, \@pagehashes );
}

# Parses the binary CBOR variant of EhViewer's .ehviewer file.
# We only need gID and token, which are usually stored as:
# {"gid": <uint>, "token": <text>, ...}
sub _parse_ehviewer_cbor {

    my ($data) = @_;

    # Quick sanity check for expected keys
    return ( "", "" ) if ( !defined($data) || length($data) < 16 );
    return ( "", "" ) if ( index( $data, "gid" ) == -1 || index( $data, "token" ) == -1 );

    my $pos = 0;
    my ( $gid, $token ) = ( "", "" );

    # Read initial item: most CBOR ehviewer blobs are a map.
    return ( "", "" ) if ( $pos >= length($data) );
    my $hdr = ord( substr( $data, $pos, 1 ) );
    $pos++;

    my $major = ( $hdr & 0xE0 ) >> 5;
    my $ai    = $hdr & 0x1F;

    # If not a map, fall back to a best-effort scan from the beginning.
    if ( $major != 5 ) {
        $pos = 0;
        $ai  = 31;    # treat as indefinite for the scan loop
    }

    # Map iteration: either definite length (count) or indefinite (ai == 31)
    my $pairs_left;
    if ( $major == 5 && $ai != 31 ) {
        my ( $count, $ok ) = _cbor_read_uint( $data, 0x00 | $ai, \$pos );
        # The above trick doesn't work for ai >= 24; handle those explicitly.
        if ( !$ok ) {
            # Reconstruct header for reading count
            ( $count, $ok ) = _cbor_read_map_count( $data, $hdr, \$pos );
        }
        return ( "", "" ) if ( !$ok );
        $pairs_left = $count;
    } else {
        $pairs_left = -1;    # indefinite
    }

    while ( $pos < length($data) ) {
        if ( $pairs_left == 0 ) {
            last;
        }

        my $b = ord( substr( $data, $pos, 1 ) );
        $pos++;

        # Break for indefinite-length maps
        last if ( $b == 0xFF );

        # Read key (usually text)
        my ( $key, $ok ) = _cbor_read_text( $data, $b, \$pos );
        if ( !$ok ) {
            # Some encoders could use byte strings as keys; try that too.
            ( $key, $ok ) = _cbor_read_bytes_as_ascii( $data, $b, \$pos );
        }
        last if ( !$ok );

        # Read value header
        last if ( $pos >= length($data) );
        my $vb = ord( substr( $data, $pos, 1 ) );
        $pos++;

        if ( $key eq 'gid' ) {
            my ( $ival, $iok ) = _cbor_read_uint( $data, $vb, \$pos );
            $gid = "$ival" if ($iok);
            _cbor_skip_item( $data, $vb, \$pos ) if ( !$iok );
        } elsif ( $key eq 'token' ) {
            my ( $tval, $tok ) = _cbor_read_text( $data, $vb, \$pos );
            if ($tok) {
                $token = $tval;
            } else {
                _cbor_skip_item( $data, $vb, \$pos );
            }
        } else {
            _cbor_skip_item( $data, $vb, \$pos );
        }

        $pairs_left-- if ( $pairs_left > 0 );
        last if ( $gid && $token );
    }

    return ( $gid, $token );
}

sub _cbor_read_map_count {
    my ( $data, $hdr, $posref ) = @_;

    my $major = ( $hdr & 0xE0 ) >> 5;
    my $ai    = $hdr & 0x1F;
    return ( "", 0 ) if ( $major != 5 || $ai == 31 );

    # The count is encoded like an uint, but with major type 5.
    # We can reuse the uint parsing by emulating the same additional-info reading.
    if ( $ai < 24 ) {
        return ( $ai, 1 );
    }
    if ( $ai == 24 ) {
        return ( "", 0 ) if ( $$posref + 1 > length($data) );
        my $v = ord( substr( $data, $$posref, 1 ) );
        $$posref += 1;
        return ( $v, 1 );
    }
    if ( $ai == 25 ) {
        return ( "", 0 ) if ( $$posref + 2 > length($data) );
        my $v = unpack( 'n', substr( $data, $$posref, 2 ) );
        $$posref += 2;
        return ( $v, 1 );
    }
    if ( $ai == 26 ) {
        return ( "", 0 ) if ( $$posref + 4 > length($data) );
        my $v = unpack( 'N', substr( $data, $$posref, 4 ) );
        $$posref += 4;
        return ( $v, 1 );
    }

    return ( "", 0 );
}

sub _cbor_read_bytes_as_ascii {
    my ( $data, $ib, $posref ) = @_;

    # Major type 2: byte string
    return ( "", 0 ) if ( ( $ib & 0xE0 ) != 0x40 );
    my $ai = $ib & 0x1F;
    return ( "", 0 ) if ( $ai == 31 );

    my $len;
    if ( $ai < 24 ) {
        $len = $ai;
    } elsif ( $ai == 24 ) {
        return ( "", 0 ) if ( $$posref + 1 > length($data) );
        $len = ord( substr( $data, $$posref, 1 ) );
        $$posref += 1;
    } elsif ( $ai == 25 ) {
        return ( "", 0 ) if ( $$posref + 2 > length($data) );
        $len = unpack( 'n', substr( $data, $$posref, 2 ) );
        $$posref += 2;
    } elsif ( $ai == 26 ) {
        return ( "", 0 ) if ( $$posref + 4 > length($data) );
        $len = unpack( 'N', substr( $data, $$posref, 4 ) );
        $$posref += 4;
    } else {
        return ( "", 0 );
    }

    return ( "", 0 ) if ( $$posref + $len > length($data) );
    my $s = substr( $data, $$posref, $len );
    $$posref += $len;

    # Best-effort; keys should be ASCII anyway.
    return ( $s, 1 );
}

sub _cbor_read_uint {
    my ( $data, $ib, $posref ) = @_;

    # Major type 0: unsigned integers
    return ( "", 0 ) if ( ( $ib & 0xE0 ) != 0x00 );

    my $ai = $ib & 0x1F;
    if ( $ai < 24 ) {
        return ( $ai, 1 );
    }
    if ( $ai == 24 ) {
        return ( "", 0 ) if ( $$posref + 1 > length($data) );
        my $v = ord( substr( $data, $$posref, 1 ) );
        $$posref += 1;
        return ( $v, 1 );
    }
    if ( $ai == 25 ) {
        return ( "", 0 ) if ( $$posref + 2 > length($data) );
        my $v = unpack( 'n', substr( $data, $$posref, 2 ) );
        $$posref += 2;
        return ( $v, 1 );
    }
    if ( $ai == 26 ) {
        return ( "", 0 ) if ( $$posref + 4 > length($data) );
        my $v = unpack( 'N', substr( $data, $$posref, 4 ) );
        $$posref += 4;
        return ( $v, 1 );
    }
    if ( $ai == 27 ) {
        return ( "", 0 ) if ( $$posref + 8 > length($data) );
        my $v = unpack( 'Q>', substr( $data, $$posref, 8 ) );
        $$posref += 8;
        return ( $v, 1 );
    }

    return ( "", 0 );
}

sub _cbor_read_text {
    my ( $data, $ib, $posref ) = @_;

    # Major type 3: text string
    return ( "", 0 ) if ( ( $ib & 0xE0 ) != 0x60 );
    my $ai = $ib & 0x1F;

    # Indefinite-length text strings exist (0x7F), but EhViewer's keys/values are definite.
    return ( "", 0 ) if ( $ai == 31 );

    my $len;
    if ( $ai < 24 ) {
        $len = $ai;
    } elsif ( $ai == 24 ) {
        return ( "", 0 ) if ( $$posref + 1 > length($data) );
        $len = ord( substr( $data, $$posref, 1 ) );
        $$posref += 1;
    } elsif ( $ai == 25 ) {
        return ( "", 0 ) if ( $$posref + 2 > length($data) );
        $len = unpack( 'n', substr( $data, $$posref, 2 ) );
        $$posref += 2;
    } elsif ( $ai == 26 ) {
        return ( "", 0 ) if ( $$posref + 4 > length($data) );
        $len = unpack( 'N', substr( $data, $$posref, 4 ) );
        $$posref += 4;
    } else {
        return ( "", 0 );
    }

    return ( "", 0 ) if ( $$posref + $len > length($data) );
    my $s = substr( $data, $$posref, $len );
    $$posref += $len;
    return ( $s, 1 );
}

sub _cbor_skip_item {
    my ( $data, $ib, $posref ) = @_;

    my $major = ( $ib & 0xE0 ) >> 5;
    my $ai    = $ib & 0x1F;

    # Unsigned / negative ints
    if ( $major == 0 || $major == 1 ) {
        # For our use case, only care about advancing correctly.
        if ( $ai < 24 ) {
            return;
        } elsif ( $ai == 24 ) {
            $$posref += 1;
            return;
        } elsif ( $ai == 25 ) {
            $$posref += 2;
            return;
        } elsif ( $ai == 26 ) {
            $$posref += 4;
            return;
        } elsif ( $ai == 27 ) {
            $$posref += 8;
            return;
        }
        return;
    }

    # Byte string / text string
    if ( $major == 2 || $major == 3 ) {
        # Definite length
        if ( $ai < 24 ) {
            $$posref += $ai;
            return;
        } elsif ( $ai == 24 ) {
            return if ( $$posref + 1 > length($data) );
            my $len = ord( substr( $data, $$posref, 1 ) );
            $$posref += 1 + $len;
            return;
        } elsif ( $ai == 25 ) {
            return if ( $$posref + 2 > length($data) );
            my $len = unpack( 'n', substr( $data, $$posref, 2 ) );
            $$posref += 2 + $len;
            return;
        } elsif ( $ai == 26 ) {
            return if ( $$posref + 4 > length($data) );
            my $len = unpack( 'N', substr( $data, $$posref, 4 ) );
            $$posref += 4 + $len;
            return;
        } elsif ( $ai == 31 ) {
            # Indefinite length: skip chunks until break
            while ( $$posref < length($data) ) {
                my $b = ord( substr( $data, $$posref, 1 ) );
                $$posref++;
                last if $b == 0xFF;
                _cbor_skip_item( $data, $b, $posref );
            }
            return;
        }
        return;
    }

    # Array / map
    if ( $major == 4 || $major == 5 ) {
        my $count;
        if ( $ai < 24 ) {
            $count = $ai;
        } elsif ( $ai == 24 ) {
            return if ( $$posref + 1 > length($data) );
            $count = ord( substr( $data, $$posref, 1 ) );
            $$posref += 1;
        } elsif ( $ai == 25 ) {
            return if ( $$posref + 2 > length($data) );
            $count = unpack( 'n', substr( $data, $$posref, 2 ) );
            $$posref += 2;
        } elsif ( $ai == 26 ) {
            return if ( $$posref + 4 > length($data) );
            $count = unpack( 'N', substr( $data, $$posref, 4 ) );
            $$posref += 4;
        } elsif ( $ai == 31 ) {
            # Indefinite length: skip items until break
            while ( $$posref < length($data) ) {
                my $b = ord( substr( $data, $$posref, 1 ) );
                $$posref++;
                last if $b == 0xFF;
                _cbor_skip_item( $data, $b, $posref );
            }
            return;
        } else {
            return;
        }

        my $items = $count;
        $items *= 2 if ( $major == 5 );    # map has key+value

        for ( 1 .. $items ) {
            return if ( $$posref >= length($data) );
            my $b = ord( substr( $data, $$posref, 1 ) );
            $$posref++;
            _cbor_skip_item( $data, $b, $posref );
        }
        return;
    }

    # Tags (semantic)
    if ( $major == 6 ) {
        # Skip the tag number, then a single item.
        if ( $ai < 24 ) {
            # ok
        } elsif ( $ai == 24 ) {
            $$posref += 1;
        } elsif ( $ai == 25 ) {
            $$posref += 2;
        } elsif ( $ai == 26 ) {
            $$posref += 4;
        } elsif ( $ai == 27 ) {
            $$posref += 8;
        }
        return if ( $$posref >= length($data) );
        my $b = ord( substr( $data, $$posref, 1 ) );
        $$posref++;
        _cbor_skip_item( $data, $b, $posref );
        return;
    }

    # Simple / floats: sizes depend on additional info
    if ( $major == 7 ) {
        if ( $ai == 24 ) { $$posref += 1; return; }
        if ( $ai == 25 ) { $$posref += 2; return; }
        if ( $ai == 26 ) { $$posref += 4; return; }
        if ( $ai == 27 ) { $$posref += 8; return; }
        return;
    }
}

sub _parse_metadata_json_file {

    my ($filepath) = @_;
    my $logger = get_plugin_logger();

    open( my $fh, '<:raw', $filepath ) or die "Could not open $filepath\n";
    local $/;
    my $text = <$fh>;
    close($fh);

    my $decoded;
    eval { $decoded = decode_json($text); };
    if ( $@ || !$decoded || ref($decoded) ne 'HASH' ) {
        $logger->debug("metadata JSON decode failed: $@");
        return ( "", "" );
    }

    my $gid   = $decoded->{gallery}->{gid};
    my $token = $decoded->{gallery}->{token};

    # Fallback: try parsing from galleryUrl if the above isn't present
    if ( ( !$gid || !$token ) && $decoded->{gallery}->{galleryUrl} ) {
        if ( $decoded->{gallery}->{galleryUrl} =~ m{/g/(\d+)/(\w+)/?} ) {
            $gid   = $1;
            $token = $2;
        }
    }

    $gid = "$gid" if defined $gid;
    $token = "$token" if defined $token;
    return ( $gid // "", $token // "" );
}

sub _parse_comicinfo_file {

    my ($filepath) = @_;

    open( my $fh, '<:encoding(UTF-8)', $filepath ) or die "Could not open $filepath\n";
    my $xml = '';
    while ( my $line = <$fh> ) {
        chomp $line;
        $xml .= $line;
    }
    close($fh);

    my $web = '';
    my $result = Mojo::DOM->new->xml(1)->parse($xml)->at('Web');
    $web = $result->text if defined $result;

    if ( $web =~ m{/g/(\d+)/(\w+)/?} ) {
        return ( $1, $2 );
    }

    return ( "", "" );
}

sub _get_tags_from_eh_api {

    my ( $ua, $gid, $token, $jpntitle, $additionaltags ) = @_;
    my $logger = get_plugin_logger();

    my $uri = 'https://api.e-hentai.org/api.php';
    my $rep = $ua->post(
        $uri => json => {
            method    => 'gdata',
            gidlist   => [ [ $gid, $token ] ],
            namespace => 1
        }
    )->result;

    die "E-H API request failed: " . $rep->message . "\n" if ( !$rep->is_success );

    my $json = $rep->json;
    die "E-H API returned invalid JSON\n" if ( !$json );
    if ( exists $json->{error} ) {
        die "E-H API error: " . $json->{error} . "\n";
    }

    my $data = $json->{gmetadata};
    die "E-H API response missing gmetadata\n" if ( !$data || ref($data) ne 'ARRAY' || !@$data );

    my @tags = @{ $data->[0]->{tags} // [] };
    my $title = $data->[0]->{ ( $jpntitle ? 'title_jpn' : 'title' ) } // "";
    if ( $title eq "" && $jpntitle ) {
        $title = $data->[0]->{title} // "";
    }
    $title = html_unescape($title);

    my $category = lc( $data->[0]->{category} // "" );
    push( @tags, "category:$category" ) if ( $category ne "" );

    if ($additionaltags) {
        my $uploader  = $data->[0]->{uploader} // "";
        my $posted_ts = $data->[0]->{posted}   // "";
        push( @tags, "uploader:$uploader" )   if ( $uploader ne "" );
        push( @tags, "timestamp:$posted_ts" ) if ( $posted_ts ne "" );
    }

    return ( \@tags, \$title );
}

# Translate EH tags to Chinese using an EhTagTranslation db.text.json.
# Format expected is compatible with https://github.com/EhTagTranslation/Database (db.text.json)
sub _translate_tag_to_cn {

    my ( $tags_ref, $db_path ) = @_;
    my $logger = get_plugin_logger();

    return $tags_ref if ( !defined($db_path) || $db_path eq "" );
    return $tags_ref if ( !-e $db_path || !-r $db_path );

    my $mtime = ( stat($db_path) )[9] // 0;

    my $db = $DB_CACHE{$db_path};
    if ( !$db || ( $db->{mtime} // 0 ) != $mtime ) {
        open( my $fh, '<:raw', $db_path ) or do {
            $logger->warn("Can't open $db_path: $!");
            return $tags_ref;
        };
        local $/;
        my $json_text = <$fh>;
        close($fh);

        my $decoded;
        eval { $decoded = decode_json($json_text); };
        if ($@ || !$decoded) {
            $logger->warn("Failed to decode JSON from $db_path: $@");
            return $tags_ref;
        }

        $db = { mtime => $mtime, json => $decoded };
        $DB_CACHE{$db_path} = $db;
    }

    my $data = $db->{json}->{data};
    return $tags_ref if ( !$data || ref($data) ne 'ARRAY' );

    # Build a namespace -> translation map for faster lookups
    my %ns_map;
    foreach my $ns (@$data) {
        next unless ref($ns) eq 'HASH';
        my $namespace = $ns->{namespace} // "";
        next if $namespace eq "";
        my $ns_name = $ns->{frontMatters}->{name} // "";
        my $ns_data = $ns->{data} // {};
        $ns_map{$namespace} = { name => $ns_name, data => $ns_data };
    }

    my @out;
    foreach my $tag (@$tags_ref) {
        my $t = $tag;
        if ( $t =~ /^([^:]+):(.*)$/ ) {
            my ( $ns, $key ) = ( $1, $2 );
            if ( exists $ns_map{$ns} ) {
                my $ns_cn = $ns_map{$ns}->{name} // $ns;
                my $key_cn = $key;
                my $ns_data = $ns_map{$ns}->{data} // {};
                if ( ref($ns_data) eq 'HASH' && exists $ns_data->{$key} ) {
                    my $name = $ns_data->{$key}->{name};
                    $key_cn = $name if ( defined($name) && $name ne "" );
                }
                $t = $ns_cn . ":" . $key_cn;
            }
        }
        push @out, $t;
    }

    return \@out;
}

1;

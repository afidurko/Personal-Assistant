import Foundation

/// Cam iOS speaker-ID contract scaffold — mirrors browser spectral gate fields.
/// Native SpeakerRecognition / embedding can replace the spectral print later;
/// keep the same `/api/turn` payload so Cam’s Aaron-only policy stays shared.
///
/// Status: contract_scaffold (see config/identity/aaron-voice-gate.json addons.ios_speaker_id)

public struct CamVoiceGateConfig: Codable, Sendable {
    public var aaronOnly: Bool
    public var noisyEnvironmentMode: Bool
    public var rejectNonAaronAsr: Bool
    public var requireEnrollmentForMic: Bool
    public var textBypass: Bool
    public var matchThreshold: Double
    public var noisyThreshold: Double
    public var raisedThreshold: Double
    public var enrollSeconds: Double
    public var storageKey: String

    public static let `default` = CamVoiceGateConfig(
        aaronOnly: true,
        noisyEnvironmentMode: true,
        rejectNonAaronAsr: true,
        requireEnrollmentForMic: true,
        textBypass: true,
        matchThreshold: 0.85,
        noisyThreshold: 0.88,
        raisedThreshold: 0.91,
        enrollSeconds: 10,
        storageKey: "cam.aaron.voice.profile.v1"
    )

    enum CodingKeys: String, CodingKey {
        case aaronOnly = "aaron_only"
        case noisyEnvironmentMode = "noisy_environment_mode"
        case rejectNonAaronAsr = "reject_non_aaron_asr"
        case requireEnrollmentForMic = "require_enrollment_for_mic"
        case textBypass = "text_bypass"
        case matchThreshold = "match_threshold"
        case noisyThreshold = "noisy_threshold"
        case raisedThreshold = "raised_threshold"
        case enrollSeconds = "enroll_seconds"
        case storageKey = "storage_key"
    }
}

public struct CamVoiceGateDecision: Sendable {
    public let accept: Bool
    public let score: Double
    public let threshold: Double
    public let reason: String
    public let multiSpeakerHint: Bool
    public let adaptive: Bool
}

/// Fields posted to Cam `/api/turn` and `/api/spike/aaron.voice`.
public struct CamVoiceGateTurnPayload: Codable, Sendable {
    public var text: String
    public var transcript: String
    public var source: String
    public var aaronVoiceScore: Double
    public var enrolled: Bool
    public var multiSpeakerHint: Bool
    public var deviceId: String

    enum CodingKeys: String, CodingKey {
        case text, transcript, source, enrolled
        case aaronVoiceScore = "aaron_voice_score"
        case multiSpeakerHint = "multi_speaker_hint"
        case deviceId = "device_id"
    }

    public init(
        text: String,
        source: String = "mic",
        aaronVoiceScore: Double,
        enrolled: Bool,
        multiSpeakerHint: Bool = false,
        deviceId: String = "ios"
    ) {
        self.text = text
        self.transcript = text
        self.source = source
        self.aaronVoiceScore = aaronVoiceScore
        self.enrolled = enrolled
        self.multiSpeakerHint = multiSpeakerHint
        self.deviceId = deviceId
    }
}

/// On-device Aaron-only gate. Replace `score` provider with SpeakerRecognition when available.
public enum CamVoiceGate {
    public static func decide(
        score: Double,
        config: CamVoiceGateConfig = .default,
        enrolled: Bool,
        multiSpeakerHint: Bool = false,
        source: String = "mic",
        adaptiveRaised: Bool = false
    ) -> CamVoiceGateDecision {
        if source == "text", config.textBypass {
            return CamVoiceGateDecision(
                accept: true,
                score: 1,
                threshold: 0,
                reason: "text_bypass",
                multiSpeakerHint: false,
                adaptive: false
            )
        }
        guard config.aaronOnly else {
            return CamVoiceGateDecision(
                accept: true,
                score: score,
                threshold: 0,
                reason: "aaron_only_disabled",
                multiSpeakerHint: multiSpeakerHint,
                adaptive: false
            )
        }
        if !enrolled, config.requireEnrollmentForMic {
            return CamVoiceGateDecision(
                accept: false,
                score: 0,
                threshold: config.matchThreshold,
                reason: "enrollment_required",
                multiSpeakerHint: false,
                adaptive: false
            )
        }
        let base =
            config.noisyEnvironmentMode || multiSpeakerHint
            ? config.noisyThreshold
            : config.matchThreshold
        let threshold = adaptiveRaised ? max(base, config.raisedThreshold) : base
        let accept = score >= threshold
        let reason: String
        if accept {
            reason = "aaron_voice_match"
        } else if multiSpeakerHint {
            reason = "rejected_surrounding_speech"
        } else {
            reason = "below_threshold"
        }
        return CamVoiceGateDecision(
            accept: accept,
            score: score,
            threshold: threshold,
            reason: reason,
            multiSpeakerHint: multiSpeakerHint,
            adaptive: adaptiveRaised
        )
    }

    public static func turnPayload(
        text: String,
        decision: CamVoiceGateDecision,
        enrolled: Bool,
        deviceId: String = "ios"
    ) -> CamVoiceGateTurnPayload {
        CamVoiceGateTurnPayload(
            text: text,
            source: "mic",
            aaronVoiceScore: decision.score,
            enrolled: enrolled,
            multiSpeakerHint: decision.multiSpeakerHint,
            deviceId: deviceId
        )
    }
}
